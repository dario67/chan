import copy
import datetime
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Union

from BuySellPoint.BS_Point import CBSPoint
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Common.ChanException import CChanException, ErrCode
from Common.CTime import CTime
from Common.func_util import check_kltype_order, kltype_lte_day
from DataAPI.CommonStockAPI import CCommonStockApi
from KLine.KLine_List import CKLine_List
from KLine.KLine_Unit import CKLine_Unit


class CChan:
    def __init__(
        self,
        code,
        begin_time=None,
        end_time=None,
        data_src: Union[DATA_SRC, str] = DATA_SRC.BAO_STOCK,
        lv_list=None,
        config=None,
        autype: AUTYPE = AUTYPE.QFQ,
        extra_kl=None
    ):
        """
        :param code: 股票代码，具体格式取决于数据源格式
        :param begin_time: 开始时间，默认为 None（至于 None 怎么理解,也取决于数据源格式）
        :param end_time: 结束时间，默认为 None（至于 None 怎么理解,也取决于数据源格式）
        :param data_src:数据源，框架提供：
            DATA_SRC.FUTU：富途
            DATA_SRC.BAO_STOCK：BaoStock(默认)
            DATA_SRC.CCXT：ccxt
            DATA_SRC.CSV: csv（具体可以看内部实现）
            "custom:文件名:类名"：自定义解析器
            框架默认提供一个 demo 为："custom: OfflineDataAPI.CStockFileReader"
            自己开发参考下文『自定义开发-数据接入』
        :param lv_list: K 线级别，必须从大到小，默认为 [KL_TYPE.K_DAY, KL_TYPE.K_60M]，可选：
            KL_TYPE.K_YEAR（-_-|| 没啥卵用，毕竟全部年线可能就只有一笔。。）
            KL_TYPE.K_QUARTER（-_-|| 季度线，同样没啥卵用）
            KL_TYPE.K_MON
            KL_TYPE.K_WEEK
            KL_TYPE.K_DAY
            KL_TYPE.K_60M
            KL_TYPE.K_30M
            KL_TYPE.K_15M
            KL_TYPE.K_5M
            KL_TYPE.K_3M
            KL_TYPE.K_1M
        :param config: CChanConfig 类，缠论元素计算参数配置，参见下文 CChanConfig
        :param autype: 复权类型，传递给获取数据接口，默认为 AUTYPE.QFQ,即前复权，可选
            AUTYPE.QFQ
            AUTYPE.HFQ
            AUTYPE.NONE
        :param extra_kl：额外K线，常用于补充 data_src 的数据，比如离线 data_src 只有到昨天为止的数据，今天开仓需要加上今天实时获得的部分K线数据；默认为 None；
            如果是个列表：每个元素必须为描述 klu 的 CKLine_Unit 类；此时如果 lv_list 参数有多个级别，则会报错
            如果是个字典，key 是 lv_list 参数里面的每个级别，value 是数组，每个元素是 CKLine_Unit 类
        """
        if lv_list is None:
            lv_list = [KL_TYPE.K_DAY, KL_TYPE.K_60M]  # TODO 为啥这是list？
        check_kltype_order(lv_list)  # lv_list顺序从高到低
        self.code = code
        self.begin_time = str(begin_time) if isinstance(begin_time, datetime.date) else begin_time
        self.end_time = str(end_time) if isinstance(end_time, datetime.date) else end_time
        self.autype = autype
        self.data_src = data_src
        self.lv_list: List[KL_TYPE] = lv_list

        if config is None:
            config = CChanConfig()
        self.conf = config

        self.kl_misalign_cnt = 0
        self.kl_inconsistent_detail = defaultdict(list)

        self.g_kl_iter = defaultdict(list)  # key是K线级别，value是对应级别的K Line Unit 的迭代器

        self.kl_datas: Dict[KL_TYPE, CKLine_List] = {}
        self.do_init()

        if not config.trigger_step:
            for _ in self.load():
                ...

    def __deepcopy__(self, memo):
        cls = self.__class__
        obj: CChan = cls.__new__(cls)
        memo[id(self)] = obj
        obj.code = self.code
        obj.begin_time = self.begin_time
        obj.end_time = self.end_time
        obj.autype = self.autype
        obj.data_src = self.data_src
        obj.lv_list = copy.deepcopy(self.lv_list, memo)
        obj.conf = copy.deepcopy(self.conf, memo)
        obj.kl_misalign_cnt = self.kl_misalign_cnt
        obj.kl_inconsistent_detail = copy.deepcopy(self.kl_inconsistent_detail, memo)
        obj.g_kl_iter = copy.deepcopy(self.g_kl_iter, memo)
        if hasattr(self, 'klu_cache'):
            obj.klu_cache = copy.deepcopy(self.klu_cache, memo)
        if hasattr(self, 'klu_last_t'):
            obj.klu_last_t = copy.deepcopy(self.klu_last_t, memo)
        obj.kl_datas = {}
        for kl_type, ckline in self.kl_datas.items():
            obj.kl_datas[kl_type] = copy.deepcopy(ckline, memo)
        for kl_type, ckline in self.kl_datas.items():
            for klc in ckline:
                for klu in klc.lst:
                    assert id(klu) in memo
                    if klu.sup_kl:
                        memo[id(klu)].sup_kl = memo[id(klu.sup_kl)]
                    memo[id(klu)].sub_kl_list = [memo[id(sub_kl)] for sub_kl in klu.sub_kl_list]
        return obj

    def do_init(self):
        self.kl_datas = {}
        for kl_type in self.lv_list:
            self.kl_datas[kl_type] = CKLine_List(kl_type, conf=self.conf)

    # def lv_name(self, lv_idx):
    #     return self.lv_list[lv_idx]

    @staticmethod
    def load_klus(stockapi_instance: CCommonStockApi, lv) -> Iterable[CKLine_Unit]:
        for klu_idx, klu in enumerate(stockapi_instance.get_kl_data()):
            klu.set_idx(klu_idx)
            klu.kl_type = lv
            yield klu

    def get_klu_iter(self, stockapi_cls, lv):
        api_instance = stockapi_cls(code=self.code, k_type=lv, begin_date=self.begin_time, end_date=self.end_time, autype=self.autype)
        return self.load_klus(api_instance, lv)

    def add_lv_iter(self, lv_name, lv_iter):
        self.g_kl_iter[lv_name].append(lv_iter)

    def get_next_lv_klu(self, lv_name):
        lv_iter = self.g_kl_iter[lv_name]
        while lv_iter:
            try:
                return next(lv_iter[0])
            except StopIteration:
                lv_iter.pop(0)
        raise StopIteration

    def step_load(self):
        print(f'start step_load ')
        assert self.conf.trigger_step
        self.do_init()  # 清空数据，防止再次重跑没有数据
        yielded = False  # 是否曾经返回过结果
        for idx, snapshot in enumerate(self.load(self.conf.trigger_step)):
            if idx < self.conf.skip_step:
                continue
            yield snapshot
            yielded = True
        if not yielded:
            yield self

    def trigger_load(self, inp):
        # 在已有pickle基础上继续计算新的
        # {type: [klu, ...]}
        if not hasattr(self, 'klu_cache'):
            self.klu_cache: List[Optional[CKLine_Unit]] = [None for _ in self.lv_list]
        if not hasattr(self, 'klu_last_t'):
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0) for _ in self.lv_list]
        for lv_idx, lv in enumerate(self.lv_list):
            if lv not in inp:
                if lv_idx == 0:
                    raise CChanException(f"最高级别{lv}没有传入数据", ErrCode.NO_DATA)
                continue
            assert isinstance(inp[lv], list)
            self.add_lv_iter(lv, iter(inp[lv]))
        for _ in self.load_iterator(lv_idx=0, parent_klu=None, step=False):
            ...
        if not self.conf.trigger_step:  # 非回放模式全部算完之后才算一次中枢和线段
            for lv in self.lv_list:
                self.kl_datas[lv].cal_seg_and_zs()

    def get_klu_iters(self, stockapi_cls):
        # 跳过一些获取数据失败的级别，只保留有效的级别
        klu_iters = []
        valid_lv_list = []
        for lv in self.lv_list:
            try:
                klu_iters.append(self.get_klu_iter(stockapi_cls, lv))
                valid_lv_list.append(lv)
            except CChanException as e:
                if e.errcode == ErrCode.SRC_DATA_NOT_FOUND and self.conf.auto_skip_illegal_sub_lv:
                    if self.conf.print_warning:
                        print(f"[WARNING-{self.code}]{lv}级别获取数据失败，跳过")
                    del self.kl_datas[lv]
                    continue
                raise e
        self.lv_list = valid_lv_list
        return klu_iters

    def _get_stock_api(self):
        print(f'load stock api {self.data_src}')
        if self.data_src == DATA_SRC.BAO_STOCK:
            from DataAPI.BaoStockAPI import CBaoStock
            return CBaoStock
        elif self.data_src == DATA_SRC.CCXT:
            from DataAPI.ccxt import CCXT
            return CCXT
        elif self.data_src == DATA_SRC.CSV:
            from DataAPI.csvAPI import CSV_API
            return CSV_API

        assert isinstance(self.data_src, str)
        if self.data_src.find("custom:") < 0:
            raise CChanException("load src type error", ErrCode.SRC_DATA_TYPE_ERR)
        package_info = self.data_src.split(":")[1]
        package_name, cls_name = package_info.split(".")
        exec(f"from DataAPI.{package_name} import {cls_name}")
        return eval(cls_name)

    def load(self, step=False):
        stockapi_cls = self._get_stock_api()
        try:
            stockapi_cls.do_init()
            for lv_idx, klu_iter in enumerate(self.get_klu_iters(stockapi_cls)):
                self.add_lv_iter(self.lv_list[lv_idx], klu_iter)
            self.klu_cache: List[Optional[CKLine_Unit]] = [None] * len(self.lv_list)
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0)] * len(self.lv_list)

            yield from self.load_iterator(lv_idx=0, parent_klu=None, step=step)  # 计算入口
            if not step:  # 非回放模式全部算完之后才算一次中枢和线段
                for lv in self.lv_list:
                    self.kl_datas[lv].cal_seg_and_zs()
        except Exception:
            raise
        finally:
            stockapi_cls.do_close()
        if len(self[0]) == 0:
            raise CChanException("最高级别没有获得任何数据", ErrCode.NO_DATA)

    def set_klu_parent_relation(self, parent_klu, kline_unit, lv_idx):
        lv_name = self.lv_list[lv_idx]
        if self.conf.kl_data_check and kltype_lte_day(lv_name) and kltype_lte_day(self.lv_list[lv_idx - 1]):
            self.check_kl_consitent(parent_klu, kline_unit)
        parent_klu.add_children(kline_unit)
        kline_unit.set_parent(parent_klu)

    def add_new_kl(self, lv_name: KL_TYPE, klu):
        try:
            self.kl_datas[lv_name].add_single_klu(klu)
        except Exception:
            if self.conf.print_err_time:
                print(f"[ERROR-{self.code}]在计算{klu.time}K线时发生错误!")
            raise

    def try_set_klu_idx(self, lv_idx: int, kline_unit: CKLine_Unit):
        if kline_unit.idx >= 0:
            return
        if len(self[lv_idx]) == 0:
            kline_unit.set_idx(0)
        else:
            kline_unit.set_idx(self[lv_idx][-1][-1].idx + 1)

    def load_iterator(self, lv_idx, parent_klu, step):
        # 递归解析 KLine Unit
        # K线时间天级别以下描述的是结束时间，如60M线，每天第一根是10点30的。天以上是当天日期
        lv_name = self.lv_list[lv_idx]
        while True:
            if self.klu_cache[lv_idx]:
                klu = self.klu_cache[lv_idx]
                assert klu is not None
                self.klu_cache[lv_idx] = None
            else:
                try:
                    klu = self.get_next_lv_klu(lv_name)
                    self.try_set_klu_idx(lv_idx, klu)
                    if not klu.time > self.klu_last_t[lv_idx]:
                        raise CChanException(f"kline time err, cur={klu.time}, last={self.klu_last_t[lv_idx]}", ErrCode.KL_NOT_MONOTONOUS)
                    self.klu_last_t[lv_idx] = klu.time
                except StopIteration:
                    break

            if parent_klu and klu.time > parent_klu.time:
                self.klu_cache[lv_idx] = klu
                break
            self.add_new_kl(lv_name, klu)
            if parent_klu:
                self.set_klu_parent_relation(parent_klu, klu, lv_idx)
            if lv_idx != len(self.lv_list)-1:
                for _ in self.load_iterator(lv_idx+1, klu, step):
                    ...
                self.check_kl_align(klu, lv_idx)
            if lv_idx == 0 and step:  # 处理最顶层的迭代器
                yield self

    def check_kl_consitent(self, parent_klu, sub_klu):
        if (parent_klu.time.year != sub_klu.time.year or
                parent_klu.time.month != sub_klu.time.month or
                parent_klu.time.day != sub_klu.time.day):
            self.kl_inconsistent_detail[str(parent_klu.time)].append(sub_klu.time)
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]父级别时间是{parent_klu.time}，次级别时间却是{sub_klu.time}")
            if len(self.kl_inconsistent_detail) >= self.conf.max_kl_inconsistent_cnt:
                raise CChanException(f"父&子级别K线时间不一致条数超过{self.conf.max_kl_inconsistent_cnt}！！", ErrCode.KL_TIME_INCONSISTENT)

    def check_kl_align(self, kline_unit, lv_idx):
        if self.conf.kl_data_check and len(kline_unit.sub_kl_list) == 0:
            self.kl_misalign_cnt += 1
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]当前{kline_unit.time}没在次级别{self.lv_list[lv_idx+1]}找到K线！！")
            if self.kl_misalign_cnt >= self.conf.max_kl_misalgin_cnt:
                raise CChanException(f"在次级别找不到K线条数超过{self.conf.max_kl_misalgin_cnt}！！", ErrCode.KL_DATA_NOT_ALIGN)

    def __getitem__(self, n) -> CKLine_List:
        if isinstance(n, KL_TYPE):  # 输入级别名字，直接获取对应级别的 CKLine_List
            return self.kl_datas[n]
        elif isinstance(n, int):  # 按照lv_list索引级别名字，获取 CKLine_List
            return self.kl_datas[self.lv_list[n]]
        raise CChanException("unsupported query type", ErrCode.COMMON_ERROR)

    def get_bsp(self, idx=None) -> List[CBSPoint]:
        """
        默认返回lv_list中最大级别的买卖点
        """
        # if idx is not None:  # TODO 没见到有这个调用啊
        #     return sorted(self[idx].bs_point_lst.lst, key=lambda x: x.klu.time)
        assert len(self.lv_list) == 1
        return sorted(self[0].bs_point_lst.lst, key=lambda x: x.klu.time)
