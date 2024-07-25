import importlib
import json
import os
import time

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, BSP_TYPE, DATA_SRC, FX_TYPE, KL_TYPE
from Common.constants import WORK_DIR
from Plot.PlotDriver import CPlotDriver

plot_config = {
    "plot_kline": True,
    "plot_kline_combine": True,
    "plot_bi": True,
    "plot_seg": True,
    "plot_eigen": False,
    "plot_zs": True,
    # "plot_macd": False,
    "plot_macd": True,
    "plot_mean": False,
    "plot_channel": False,
    "plot_bsp": True,
    "plot_extrainfo": False,
    "plot_demark": False,
    "plot_marker": False,
    "plot_rsi": False,
    "plot_kdj": False,
}

plot_para = {
    "seg": {
        # "plot_trendline": True,
    },
    "bi": {
        # "show_num": True,
        # "disp_end": True,
    },
    "figure": {
        "x_range": 200,
    },
    "marker": {
        # "markers": {  # text, position, color
        #     '2023/06/01': ('marker here', 'up', 'red'),
        #     '2023/06/08': ('marker here', 'down')
        # },
    }
}


def write_file(file_name, context, mode='w'):
    f = open(file_name, mode)
    f.write(context)
    f.close()


class Backtest:
    def __init__(self, config):
        self.config = config

    def run_backtest(self, plot=False):
        # 根据配置的策略名称执行策略
        strategy_name = self.config.get('strategy')
        strategy_class = self._get_strategy_class(strategy_name)

        print(f"开始回测 {self.config['code']} {self.config['lv_list']} 策略：{strategy_name}")

        chan = CChan(
            code=self.config['code'],
            begin_time=self.config['begin_time'],
            end_time=self.config['end_time'],
            data_src=self.config['data_src'],
            lv_list=self.config['lv_list'],
            config=self.config['config'],
            autype=AUTYPE.QFQ,
        )

        strategy = strategy_class()
        for chan_snapshot in chan.step_load():  # 每增加一根K线，返回当前静态精算结果
            # strategy.execute_buy(chan=chan_snapshot)
            strategy.execute(chan=chan_snapshot)

        # 分析回测结果
        self._analyze_backtest_result(strategy.get_result())

        if plot:
            # 画图
            plot_driver = CPlotDriver(
                chan,
                plot_config=plot_config,
                plot_para=plot_para,
            )
            print(f'init plot_driver success')

            plot_driver.figure.show()
            plot_driver.save2img(f"/Users/paopao/Documents/chan_plot/{self.config['code']}.jpg")

    def _get_strategy_class(self, strategy_name):
        module_name = 'Strategy.' + strategy_name
        try:
            module = importlib.import_module(module_name)
            print('import ok')
            strategy_class = getattr(module, strategy_name)
            return strategy_class
        except (ImportError, AttributeError):
            raise ValueError(f"Strategy '{strategy_name}' not found")

    def _analyze_backtest_result(self, result):
        # 分析回测结果的逻辑，生成回测报告
        result['code'] = self.config['code']
        print(json.dumps(result, ensure_ascii=False))
        write_file(f"/Users/paopao/backtext.txt", json.dumps(result, ensure_ascii=False) + '\n', mode='a')


def run_one(code):
    backtest_conf = {
        "code": f"sz.{code}",
        "begin_time": "2022-01-18",
        "end_time": "2024-07-04",
        "data_src": DATA_SRC.BAO_STOCK,
        "lv_list": [KL_TYPE.K_60M],
        "config": CChanConfig({
            "trigger_step": True,  # 打开开关！
            "divergence_rate": 0.8,
            "min_zs_cnt": 1,
        }),
        'strategy': 'Eg',
    }
    try:
        b = Backtest(backtest_conf)
        b.run_backtest()
    except Exception as e:
        return


if __name__ == "__main__":
    # run_one('300671')

    for line in open(f'{WORK_DIR}/sz.txt', 'r'):
        code = line.strip()
        print(code)
        run_one(code)
        time.sleep(0.5)

    # exit(0)

