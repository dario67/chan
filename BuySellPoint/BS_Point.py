from typing import Dict, Generic, List, Optional, TypeVar, Union

from Bi.Bi import CBi
from ChanModel.Features import CFeatures
from Common.CEnum import BSP_TYPE
from Seg.Seg import CSeg

LINE_TYPE = TypeVar('LINE_TYPE', CBi, CSeg)


class CBSPoint(Generic[LINE_TYPE]):
    """
    买卖点类
    """
    def __init__(self, bi: LINE_TYPE, is_buy, bs_type: BSP_TYPE, relate_bsp1: Optional['CBSPoint'], feature_dict=None):
        self.bi: LINE_TYPE = bi  # 所属的笔（买卖点一定在某一笔末尾）
        self.klu = bi.get_end_klu()  # 笔末尾的K线，即买卖点所在K线
        self.is_buy = is_buy  # True为买点，False为卖点
        self.type: List[BSP_TYPE] = [bs_type]  # 买卖点类别，是个数组，比如2，3类买卖点是同一个
        self.relate_bsp1 = relate_bsp1

        self.bi.bsp = self  # type: ignore
        self.features = CFeatures(feature_dict)

        self.is_segbsp = False

    def add_type(self, bs_type: BSP_TYPE):
        self.type.append(bs_type)

    def type2str(self):
        return ",".join([x.value for x in self.type])

    def add_another_bsp_prop(self, bs_type: BSP_TYPE, relate_bsp1):
        self.add_type(bs_type)
        if self.relate_bsp1 is None:
            self.relate_bsp1 = relate_bsp1
        elif relate_bsp1 is not None:
            assert self.relate_bsp1.klu.idx == relate_bsp1.klu.idx

    def add_feat(self, inp1: Union[str, Dict[str, float], Dict[str, Optional[float]], 'CFeatures'], inp2: Optional[float] = None):
        self.features.add_feat(inp1, inp2)
