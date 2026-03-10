"""
测试语言管理器功能
"""
import os
import sys

# 设置控制台编码为UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 设置语言为英文
os.environ['APP_LANGUAGE'] = 'en_US'

# 导入语言管理器
from language_manager import t, set_language, get_current_language

print("=" * 60)
print("语言管理器测试")
print("=" * 60)

# 测试1：获取当前语言
print(f"\n当前语言: {get_current_language()}")

# 测试2：英文翻译
print("\n英文翻译测试:")
print(f"  窗口标题: {t('ui.window_title')}")
print(f"  控制面板: {t('ui.control_panel')}")
print(f"  开始监控: {t('ui.start_monitor')}")
print(f"  停止监控: {t('ui.stop_monitor')}")
print(f"  工厂模式: {t('ui.factory_mode')}")

# 测试3：状态位名称
print("\n状态位名称:")
print(f"  Pack过压(告警): {t('status_bits.alarm.pack_ov')}")
print(f"  充电过流(保护): {t('status_bits.protect.chg_oc')}")
print(f"  电压传感失效(故障): {t('status_bits.fault.v_sensor')}")

# 测试4：窗口标题
print("\n窗口标题:")
print(f"  SBS数据: {t('windows.sbs')}")
print(f"  BMS参数: {t('windows.bms')}")
print(f"  校准参数: {t('windows.kb')}")

# 测试5：变量名（带格式化）
print("\n变量名（带格式化）:")
print(f"  PACK电压: {t('var_templates.pack_voltage')}")
print(f"  第5节电压: {t('var_templates.cell_voltage', 5)}")
print(f"  环境温度3: {t('var_templates.temp', 3)}")

# 测试6：切换到中文
print("\n" + "=" * 60)
print("切换到中文")
print("=" * 60)
set_language('zh_CN')
print(f"当前语言: {get_current_language()}")

print("\n中文翻译测试:")
print(f"  窗口标题: {t('ui.window_title')}")
print(f"  控制面板: {t('ui.control_panel')}")
print(f"  开始监控: {t('ui.start_monitor')}")
print(f"  停止监控: {t('ui.stop_monitor')}")

print("\n状态位名称:")
print(f"  Pack过压(告警): {t('status_bits.alarm.pack_ov')}")
print(f"  充电过流(保护): {t('status_bits.protect.chg_oc')}")
print(f"  电压传感失效(故障): {t('status_bits.fault.v_sensor')}")

print("\n变量名（带格式化）:")
print(f"  PACK电压: {t('var_templates.pack_voltage')}")
print(f"  第5节电压: {t('var_templates.cell_voltage', 5)}")
print(f"  环境温度3: {t('var_templates.temp', 3)}")

# 测试7：测试struct_model
print("\n" + "=" * 60)
print("测试 struct_model.py 集成")
print("=" * 60)

# 切换回英文测试
set_language('en_US')
from struct_model import STATUS_BIT_NAMES, BATTERY_STATUS_NAMES, STRUCT_VARIABLES

print(f"当前语言: {get_current_language()}")
print("\n状态位名称（来自struct_model）:")
print(f"  ALARM_PACK_OV: {STATUS_BIT_NAMES['ALARM'][0x00000001]}")
print(f"  PROTECT_CHG_OC: {STATUS_BIT_NAMES['PROTECT'][0x00000040]}")

print("\n电池状态名称:")
print(f"  空闲: {BATTERY_STATUS_NAMES[0x00]}")
print(f"  充电: {BATTERY_STATUS_NAMES[0x01]}")

print("\nPC_GET_SBS 前5个变量:")
for i, var in enumerate(STRUCT_VARIABLES['PC_GET_SBS'][:5]):
    print(f"  {i+1}. {var}")

# 切换到中文
set_language('zh_CN')
# 重新导入以应用新语言
import importlib
import struct_model
importlib.reload(struct_model)
from struct_model import STATUS_BIT_NAMES as STATUS_CN, STRUCT_VARIABLES as VARS_CN

print(f"\n切换到中文，当前语言: {get_current_language()}")
print("\n状态位名称（中文）:")
print(f"  ALARM_PACK_OV: {STATUS_CN['ALARM'][0x00000001]}")
print(f"  PROTECT_CHG_OC: {STATUS_CN['PROTECT'][0x00000040]}")

print("\nPC_GET_SBS 前5个变量（中文）:")
for i, var in enumerate(VARS_CN['PC_GET_SBS'][:5]):
    print(f"  {i+1}. {var}")

print("\n" + "=" * 60)
print("✅ 所有测试完成！")
print("=" * 60)

