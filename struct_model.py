import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
import struct
from intelhex import IntelHex
from log_controller import LogManager
from PyQt6.QtCore import pyqtSignal
import json
import os
import re

import traceback
# Define constants at the top of your file
CELL_COUNT = 16  # Adjust this value as needed
TEMP_COUNT = 5   # Adjust this value as needed

# ======================== 状态位定义（位掩码）========================
# 告警状态位 (ALARM)
ALARM_PACK_OV = 0x00000001
ALARM_BATT_OV = 0x00000002
ALARM_CELL_OV = 0x00000004
ALARM_BATT_UV = 0x00000010
ALARM_CELL_UV = 0x00000020
ALARM_CHG_OC = 0x00000040
ALARM_DIS_OC = 0x00000080
ALARM_CHG_OT = 0x00000100
ALARM_DIS_OT = 0x00000200
ALARM_CHG_UT = 0x00000400
ALARM_DIS_UT = 0x00000800
ALARM_SOC_L = 0x00001000
ALARM_END_LIFE = 0x00010000
ALARM_MOS_HT = 0x00020000

# 保护状态位 (PROTECT)
PROTECT_PACK_OV = 0x00000001
PROTECT_BATT_OV = 0x00000002
PROTECT_CELL_OV = 0x00000004
PROTECT_BATT_UV = 0x00000010
PROTECT_CELL_UV = 0x00000020
PROTECT_CHG_OC = 0x00000040
PROTECT_DIS_OC = 0x00000080
PROTECT_CHG_OT = 0x00000100
PROTECT_DIS_OT = 0x00000200
PROTECT_CHG_UT = 0x00000400
PROTECT_DIS_UT = 0x00000800
PROTECT_SHORT = 0x00004000
PROTECT_REV = 0x00008000
PROTECT_CHG_UTOC = 0x00010000
PROTECT_CHG_UTOV = 0x00040000
PROTECT_CHG_SHORT = 0x00080000
PROTECT_PSP = 0x00100000
PROTECT_BQ_SCD = 0x00200000  # BQ769X0检测短路
PROTECT_BQ_OCD = 0x00400000  # BQ769X0检测放电过流
PROTECT_MOS_HT = 0x00800000
PROTECT_CHG_UT_LIMIT = 0x01000000  # 充电低温极限保护值

# 失效状态位 (FAULT)
FAULT_V_SENSOR = 0x00000001
FAULT_T_SENSOR = 0x00000002
FAULT_CHG = 0x00000004
FAULT_DIS = 0x00000008
FAULT_CELL_BAD = 0x00000010
FAULT_SWITCH_OFF = 0x00000080
FAULT_LIFE_END = 0x00000100
FAULT_BQ_UV = 0x00010000  # BQ769X0二次保护欠压
FAULT_BQ_OV = 0x00020000  # BQ769X0二次保护过压
FAULT_BQ_DEVIECE = 0x00040000  # BQ769X0芯片失效
FAULT_BQ_OVERWR = 0x00080000  # BQ769X0芯片失效
FAULT_FUSE_BREAK = 0x00100000  # 保险丝熔断异常

# 其他信息状态位 (INFO)
INFO_HEAETER_CONFIG = 0x00000001
INFO_HEATER_ON = 0x00000002
INFO_CHG_FULL_T = 0x00000004
INFO_BATT_FULL = 0x00000008
INFO_CHG_LIMITED_ON = 0x00000010
INFO_DIS_LIMITED_ON = 0x00000020
INFO_CHG_MOS_OFF = 0x00000040
INFO_DIS_MOS_OFF = 0x00000080
INFO_LOWVOL_LIMIT = 0x00000100
INFO_LOWTEMP_FORCECHG = 0x00000200
INFO_MULT_BATT = 0x00000400
INFO_CAN_MASTER = 0x00000800
INFO_CAN_SLAVE = 0x00001000
INFO_CALENDAR_REACH = 0x00002000
INFO_TEST_KB = 0x00004000
INFO_CALIBRATED_V = 0x00008000
INFO_CALIBRATED_C = 0x00010000
INFO_LOST_CANBOX = 0x00020000
INFO_NO_INV_TIMEOUTE = 0x00040000
INFO_FUSEEN_OPEN = 0x00080000
INFO_CELL_CTO = 0x00100000
INFO_PSWFUNCTION_ON = 0x00200000
INFO_POWERSAVE_ON = 0x00400000
INFO_FORCEDDIS_ON = 0x00800000
INFO_HEATERMODE_SELF = 0x01000000

# 充放电状态 (STATUS)
STATUS_IDLE = 0x00
STATUS_CHG = 0x01
STATUS_DIS = 0x02
STATUS_FULL = 0x04

# 状态位名称映射字典（统一5个中文字符，header已区分类型）
STATUS_BIT_NAMES = {
    # 告警状态 (ALARM)
    'ALARM': {
        ALARM_PACK_OV: 'Pack过压',
        ALARM_BATT_OV: 'Batt过压',
        ALARM_CELL_OV: '电芯过压',
        ALARM_BATT_UV: 'Batt欠压',
        ALARM_CELL_UV: '电芯欠压',
        ALARM_CHG_OC: '充电过流',
        ALARM_DIS_OC: '放电过流',
        ALARM_CHG_OT: '充电过温',
        ALARM_DIS_OT: '放电过温',
        ALARM_CHG_UT: '充电低温',
        ALARM_DIS_UT: '放电低温',
        ALARM_SOC_L: 'SOC过低',
        ALARM_END_LIFE: '寿命终止',
        ALARM_MOS_HT: 'MOS过热',
    },
    # 保护状态 (PROTECT)
    'PROTECT': {
        PROTECT_PACK_OV: 'Pack过压',
        PROTECT_BATT_OV: 'Batt过压',
        PROTECT_CELL_OV: '电芯过压',
        PROTECT_BATT_UV: 'Batt欠压',
        PROTECT_CELL_UV: '电芯欠压',
        PROTECT_CHG_OC: '充电过流',
        PROTECT_DIS_OC: '放电过流',
        PROTECT_CHG_OT: '充电过温',
        PROTECT_DIS_OT: '放电过温',
        PROTECT_CHG_UT: '充电低温',
        PROTECT_DIS_UT: '放电低温',
        PROTECT_SHORT: '短路保护',
        PROTECT_REV: '反接保护',
        PROTECT_CHG_UTOC: '充电低温过流',
        PROTECT_CHG_UTOV: '充电低温过压',
        PROTECT_CHG_SHORT: '充电短路',
        PROTECT_PSP: 'PSP保护',
        PROTECT_BQ_SCD: 'BQ短路',
        PROTECT_BQ_OCD: 'BQ过流',
        PROTECT_MOS_HT: 'MOS过热',
        PROTECT_CHG_UT_LIMIT: '充电低温极限',
    },
    # 失效状态 (FAULT)
    'FAULT': {
        FAULT_V_SENSOR: '电压传感失效',
        FAULT_T_SENSOR: '温度传感失效',
        FAULT_CHG: '充电管失效',
        FAULT_DIS: '放电管失效',
        FAULT_CELL_BAD: '电芯失效',
        FAULT_SWITCH_OFF: '开关失效',
        FAULT_LIFE_END: '寿命终止',
        FAULT_BQ_UV: 'BQ欠压',
        FAULT_BQ_OV: 'BQ过压',
        FAULT_BQ_DEVIECE: 'BQ芯片',
        FAULT_BQ_OVERWR: 'BQ覆写',
        FAULT_FUSE_BREAK: '保险丝断',
    },
    # 其他信息 (INFO)
    'INFO': {
        INFO_HEAETER_CONFIG: '加热模式',
        INFO_HEATER_ON: '加热开启',
        INFO_CHG_FULL_T: '临时满充',
        INFO_BATT_FULL: '真正满充',
        INFO_CHG_LIMITED_ON: '充电限流开',
        INFO_DIS_LIMITED_ON: '放电限流开',
        INFO_CHG_MOS_OFF: '充MOS关',
        INFO_DIS_MOS_OFF: '放MOS关',
        INFO_LOWVOL_LIMIT: '低压限制',
        INFO_LOWTEMP_FORCECHG: '低温强充',
        INFO_MULT_BATT: '多电池组',
        INFO_CAN_MASTER: 'CAN主机',
        INFO_CAN_SLAVE: 'CAN从机',
        INFO_CALENDAR_REACH: '日历到期',
        INFO_TEST_KB: '测试模式',
        INFO_CALIBRATED_V: '电压已校准',
        INFO_CALIBRATED_C: '电流已校准',
        INFO_LOST_CANBOX: 'CAN丢失',
        INFO_NO_INV_TIMEOUTE: '无逆变器',
        INFO_FUSEEN_OPEN: '保险丝开',
        INFO_CELL_CTO: '电芯CTO',
        INFO_PSWFUNCTION_ON: '保电功能开',
        INFO_POWERSAVE_ON: '保电中',
        INFO_FORCEDDIS_ON: '强制放电',
        INFO_HEATERMODE_SELF: '自加热',
    },
    # 均衡状态 (BALANCE) - 每一位代表一个电芯的均衡状态
    'BALANCE': {
        0x00000001: '01号芯',
        0x00000002: '02号芯',
        0x00000004: '03号芯',
        0x00000008: '04号芯',
        0x00000010: '05号芯',
        0x00000020: '06号芯',
        0x00000040: '07号芯',
        0x00000080: '08号芯',
        0x00000100: '09号芯',
        0x00000200: '10号芯',
        0x00000400: '11号芯',
        0x00000800: '12号芯',
        0x00001000: '13号芯',
        0x00002000: '14号芯',
        0x00004000: '15号芯',
        0x00008000: '16号芯',
    }
}

# 充放电状态名称
BATTERY_STATUS_NAMES = {
    STATUS_IDLE: '空闲',
    STATUS_CHG: '充电',
    STATUS_DIS: '放电',
    STATUS_FULL: '已满'
}


def parse_status_bits(status_value, status_type='ALARM'):
    """
    解析状态寄存器值为单个状态位列表

    Args:
        status_value: 状态寄存器的值（32位整数）
        status_type: 状态类型 'ALARM', 'PROTECT', 'FAULT', 'INFO'

    Returns:
        list: 状态位列表，每项格式 {'name': str, 'value': int, 'bit': int}
    """
    if status_type not in STATUS_BIT_NAMES:
        return []

    bit_map = STATUS_BIT_NAMES[status_type]
    result = []

    for bit_mask, name in bit_map.items():
        # 检查该位是否被置起
        is_set = 1 if (status_value & bit_mask) != 0 else 0

        # 计算位位置（用于调试）
        bit_position = (bit_mask & -bit_mask).bit_length() - 1

        result.append({
            'name': name,
            'value': is_set,
            'bit': bit_position,
            'mask': bit_mask
        })

    return result


def parse_all_status_from_sbs(sbs_data_dict):
    """
    从 PC_GET_SBS 数据字典中解析所有状态位

    Args:
        sbs_data_dict: PC_GET_SBS 解析后的字典，包含 告警状态, 保护状态 等

    Returns:
        dict: 包含所有状态位的字典
            {
                'alarm': [...],
                'protect': [...],
                'fault': [...],
                'info': [...],
                'balance': [...],
                'battery_status': str
            }
    """
    result = {}

    # 解析告警状态
    if '告警状态' in sbs_data_dict:
        result['alarm'] = parse_status_bits(sbs_data_dict['告警状态'], 'ALARM')

    # 解析保护状态
    if '保护状态' in sbs_data_dict:
        result['protect'] = parse_status_bits(sbs_data_dict['保护状态'], 'PROTECT')

    # 解析失效状态
    if '失效状态' in sbs_data_dict:
        result['fault'] = parse_status_bits(sbs_data_dict['失效状态'], 'FAULT')

    # 解析其他信息
    if '其他信息' in sbs_data_dict:
        result['info'] = parse_status_bits(sbs_data_dict['其他信息'], 'INFO')

    # 解析均衡状态
    if '均衡状态' in sbs_data_dict:
        result['balance'] = parse_status_bits(sbs_data_dict['均衡状态'], 'BALANCE')

    # 解析电池状态
    if '电池状态' in sbs_data_dict:
        batt_status = sbs_data_dict['电池状态']
        result['battery_status'] = BATTERY_STATUS_NAMES.get(batt_status, f'未知({batt_status})')

    return result


def get_all_status_bits_for_display(sbs_data_dict):
    """
    从 PC_GET_SBS 数据中提取所有状态位，格式化为适合 StatusBitsWidget 显示的格式
    按类型分组，同类型在同一列显示

    Args:
        sbs_data_dict: PC_GET_SBS 解析后的字典

    Returns:
        list: 状态位列表，每项格式 {'name': str, 'value': int, 'type': str}，适合直接传给 update_status_bits()
    """
    all_status = parse_all_status_from_sbs(sbs_data_dict)
    display_list = []

    # 添加告警状态
    if 'alarm' in all_status:
        for bit in all_status['alarm']:
            display_list.append({'name': bit['name'], 'value': bit['value'], 'type': 'alarm'})

    # 添加保护状态
    if 'protect' in all_status:
        for bit in all_status['protect']:
            display_list.append({'name': bit['name'], 'value': bit['value'], 'type': 'protect'})

    # 添加失效状态
    if 'fault' in all_status:
        for bit in all_status['fault']:
            display_list.append({'name': bit['name'], 'value': bit['value'], 'type': 'fault'})

    # 添加其他信息
    if 'info' in all_status:
        for bit in all_status['info']:
            display_list.append({'name': bit['name'], 'value': bit['value'], 'type': 'info'})

    return display_list


def get_alarm_protect_display_data(sbs_data_dict):
    """
    获取告警-保护信息窗口的显示数据
    告警和保护按照状态位的位置对应起来，没有的用"-"替代
    
    Args:
        sbs_data_dict: PC_GET_SBS 解析后的字典
        
    Returns:
        list: 数据列表，每项格式 (告警名称, 告警值, 保护名称, 保护值)
    """
    all_status = parse_all_status_from_sbs(sbs_data_dict)
    
    # 创建告警和保护的位索引映射
    alarm_by_bit = {}
    protect_by_bit = {}
    
    if 'alarm' in all_status:
        for bit_info in all_status['alarm']:
            alarm_by_bit[bit_info['bit']] = {
                'name': bit_info['name'],
                'value': bit_info['value']
            }
    
    if 'protect' in all_status:
        for bit_info in all_status['protect']:
            protect_by_bit[bit_info['bit']] = {
                'name': bit_info['name'],
                'value': bit_info['value']
            }
    
    # 获取所有位索引的并集
    all_bits = sorted(set(alarm_by_bit.keys()) | set(protect_by_bit.keys()))
    
    # 构建显示数据
    result = []
    for bit_idx in all_bits:
        alarm_data = alarm_by_bit.get(bit_idx, {'name': '-', 'value': 0})
        protect_data = protect_by_bit.get(bit_idx, {'name': '-', 'value': 0})
        
        result.append((
            alarm_data['name'],
            str(alarm_data['value']),
            protect_data['name'],
            str(protect_data['value'])
        ))
    
    return result


def get_other_status_display_data(sbs_data_dict):
    """
    获取其他状态信息窗口的显示数据
    错误、信息、均衡每个单独一列
    
    Args:
        sbs_data_dict: PC_GET_SBS 解析后的字典
        
    Returns:
        list: 数据列表，每项格式 (错误名称, 错误值, 信息名称, 信息值, 均衡名称, 均衡值)
    """
    all_status = parse_all_status_from_sbs(sbs_data_dict)
    
    fault_list = []
    info_list = []
    balance_list = []
    
    if 'fault' in all_status:
        for bit_info in all_status['fault']:
            fault_list.append({
                'name': bit_info['name'],
                'value': bit_info['value']
            })
    
    if 'info' in all_status:
        for bit_info in all_status['info']:
            info_list.append({
                'name': bit_info['name'],
                'value': bit_info['value']
            })
    
    if 'balance' in all_status:
        for bit_info in all_status['balance']:
            balance_list.append({
                'name': bit_info['name'],
                'value': bit_info['value']
            })
    
    # 找到最大行数
    max_len = max(len(fault_list), len(info_list), len(balance_list))
    
    # 构建显示数据
    result = []
    for i in range(max_len):
        fault_data = fault_list[i] if i < len(fault_list) else {'name': '-', 'value': 0}
        info_data = info_list[i] if i < len(info_list) else {'name': '-', 'value': 0}
        balance_data = balance_list[i] if i < len(balance_list) else {'name': '-', 'value': 0}
        
        result.append((
            fault_data['name'],
            str(fault_data['value']),
            info_data['name'],
            str(info_data['value']),
            balance_data['name'],
            str(balance_data['value'])
        ))
    
    return result


def get_battery_status_display_data(sbs_data_dict):
    """
    获取电池状态窗口的显示数据
    
    Args:
        sbs_data_dict: PC_GET_SBS 解析后的字典
        
    Returns:
        list: 数据列表，每项格式 [name, value]（2列数据）
    """
    all_status = parse_all_status_from_sbs(sbs_data_dict)
    
    result = []
    
    # 添加电池状态（使用2列格式）
    if 'battery_status' in all_status:
        result.append(['电池状态', all_status['battery_status']])
    
    return result


# ---------------------------- 结构体定义 ----------------------------
# 注意：所有格式字符串均已展开为具体字符，确保顺序严格匹配
STRUCT_FORMATS = {
    "PC_GET_BMS": "<"
        "LLLLLLLLLLLL"  # ulCHG_SwitchV(4) ~ ulBatt_OVP_Resume(4)
        "HHHH"
        "LLLL"
        "HHHH"
        "llllll"
        "hhhhhhhhhhhhhhhh"
        "hh",
    "PC_GET_KB": "<"
        "HH"
        "HHHHHHHHHHHHHHHH"
        "HhHhHhHhHhHh"
        "HHHHHHHH",
    "PC_GET_OCP_DELAYTIME": "<HHHH",
    "PC_GET_CELL_CAP_PARA": "<LL",
    "PC_GET_MOSHTDATA": "<HHHH",
    "PC_GET_LIFE_PARA": "<HHLLL",
    "PC_GET_SBS": "<LL"  # PACK电压, BATT电压
        "HHHHHHHHHHHHHHHH"  # 第1-16节电压
        "l"  # 电流
        "hhhhh"  # 环境温度1-5
        "HHH"  # 剩余容量, 满充容量, 设计容量
        "LLLLL"  # 其他信息, 告警状态, 保护状态, 失效状态, 均衡状态
        "HH"  # 电池状态, SOC
        "LLL",  # 容量保持率, 放电次数, 总放电容量
    "PC_GET_VER": "<"
        "HHHH"    # 主版本号, 次版本号, 修订版本号, 编译年份
        "BB"      # 编译月份, 编译日期
        "30s"     # 硬件版本 (30 bytes)
        "40s",    # 功能版本 (40 bytes)
    "PC_GET_INF": "<"
        "HHHHBBBB"  # TVER: bootVer
        "HHHHBBBB"  # TVER: app_Ver
        "HHHHBBBB"  # TVER: buffVer
        "HHHHBBBB"  # TVER: backVer
        "15s"     # icName (15 bytes)
        "B"       # writableArea (1 byte)
        "L"       # pcAddr (4 bytes)
        "L",      # uniqueID (4 bytes)
    "PC_GET_SERIALNUM": "<30s",  # 序列号：30字节字符串
    "PC_SET_SERIALNUM": "<30s",  # 序列号：30字节字符串
    "PC_GET_FUSESTATE": "<HH",  # 保险丝信息：使能状态、保险丝状态
    "PC_SET_FUSESTATE": "<HH",  # 保险丝信息：使能状态、保险丝状态
    "PC_GET_CLUSTER_SBS": "<"
        "BB"  # byBrand, byCurrRate
        "H"   # wBattModuleCap
        "L"   # dwClusterCap
        "HH"  # byTotalBatteryNum, wComFailCount
        "HH"  # wBmsFailCount, wCellFailCount
        "HH"  # wChgMosOffCount, wDisMosOffCnout
        "hh"  # sSysMaxCellTemp, sSysMinCellTemp
        "HH"  # usSysMaxCellVolt, usSysMinCellVolt
        "LL"  # ulSysMaxBattVolt, ulSysMinBattVolt
        "ll"  # lSysMaxCurrent, lSysMinCurrent
        "HH"  # usSysMaxSOC, usSysMinSOC
        "HH"  # usSysMaxSOH, usSysMinSOH
        "HH"  # usClusterChgVoltLimit, usClusterDisVoltLimit
        "LL"  # dwClusterChgCurLimit, dwClusterDisCurLimit
        "h"   # sClusterTemp
        "H"   # usClusterVoltInV
        "l"   # lClusterCurrInA
        "HH"  # usClusterSoc, usClusterSoh
        "LL"  # ulClusterProtect, ulClusterFault
        "L"   # ulClusterCycles
        "HHHHHHHHHH",  # wReserve[10]
}

STRUCT_ADDRESSES = {
    "PC_GET_BMS": 0x500202,
    "PC_GET_KB": 0x5002C2,
    "PC_GET_OCP_DELAYTIME": 0x500322,
    "PC_GET_CELL_CAP_PARA": 0x500332,
    "PC_GET_MOSHTDATA": 0x500342,
    "PC_GET_LIFE_PARA": 0x500402
}

STRUCT_VARIABLES = {
    "PC_GET_BMS": [
        "充电功耗电压值", "充电功耗Pack与Batt压差",
        "充电功满开启电压值", "充电功满停止电压值",
        "Pack过充-警限值", "Pack过充-警恢复值",
        "Pack过充-保限值", "Pack过充-保恢复值",
        "Batt过充-警限值", "Batt过充-警恢复值",
        "Batt过充-保限值", "Batt过充-保恢复值",
        "Cell过充-警限值", "Cell过充-警恢复值",
        "Cell过充-保限值", "Cell过充-保恢复值",
        "Batt欠压-警限值", "Batt欠压-警恢复值",
        "Batt欠压-保限值", "Batt欠压-保恢复值",
        "Cell欠压-警限值", "Cell欠压-警恢复值",
        "Cell欠压-保限值", "Cell欠压-保恢复值",
        "充-过流-警限值", "充-过流-警恢复值", "充-过流-保护限值",
        "放-过流-警限值", "放-过流-警恢复值", "放-过流-保护限值",
        "充-过温-警限值", "充-过温-警恢复值", "充-过温-保护限值", "充-过温-保护恢复值",
        "放-过温-警限值", "放-过温-警恢复值", "放-过温-保护限值", "放-过温-保护恢复值",
        "充-低温-警限值", "充-低温-警恢复值", "充-低温-保护限值", "充-低温-保护恢复值",
        "放-低温-警限值", "放-低温-警恢复值", "放-低温-保护限值", "放-低温-保护恢复值",
        "加热器启动温度", "加热器关闭温度",
    ],
    "PC_GET_KB": [
        "Pack电压K", "Batt电压K",
        *[f"第【{i+1}】节电压K" for i in range(16)],
        "50-500安K(注，不同电池，电流范围不同，谨慎参考)",    "50-500安B",
        "-(50-500)安K", "-(50-500)安B",
        "10-50安SK",    "10-50安SB",
        "-10-50安SK",   "-10-50安SB",
        "0-10安SSK",    "0-10安SSB",
        "-(0-10)安SSK", "-(0-10)安SSB",
        *[f"温度{i+1}K" for i in range(8)]
    ],
    "PC_GET_OCP_DELAYTIME": [
        "1C充电过流保护延时", "2C充电过流保护延时",
        "1C放电过流保护延时", "2C放电过流保护延时"
    ],
    "PC_GET_CELL_CAP_PARA": [
        "额定容量", "出厂容量"
    ],
    "PC_GET_MOSHTDATA": [
        "MOS温度告警", "MOS温度告警恢复", "MOS温度保护", "MOS温度保护恢复"
    ],
    "PC_GET_LIFE_PARA": [
        "SOC", "保留", "容量保持率",
        "循环时间累计", "单次充电结合容量"
    ],
    "PC_GET_SBS": [
        "PACK电压", "BATT电压",
        *[f"第【{i+1}】节电压" for i in range(16)],
        "电流",
        *[f"环境温度{i+1}" for i in range(5)],
        "剩余容量", "满充容量", "设计容量",
        "其他信息", "告警状态", "保护状态", "失效状态", "均衡状态",
        "电池状态", "SOC",
        "容量保持率", "放电次数", "总放电容量"
    ],
    "PC_GET_VER": [
        "主版本号", "次版本号", "修订版本号", "编译年份",
        "编译月份", "编译日期",
        "硬件版本",
        "功能版本"
    ],
    "PC_GET_INF": [
        "boot主版本号", "boot次版本号", "boot修订版本号", "boot年份", "boot月份", "boot日期","boot保留1","boot保留2",
        "app主版本号",  "app次版本号",  "app修订版本号",   "app年份",  "app月份",  "app日期", "app保留1", "app保留2",
        "buff主版本号", "buff次版本号", "buff修订版本号", "buff年份", "buff月份", "buff日期","buff保留1","buff保留2",
        "back主版本号", "back次版本号", "back修订版本号", "back年份", "back月份", "back日期","back保留1","back保留2",
        "芯片名称",
        "可写区域",
        "PC地址",
        "唯一ID"
    ],
    "PC_GET_SERIALNUM": [
        "序列号"
    ],
    "PC_SET_SERIALNUM": [
        "序列号"
    ],
    "PC_GET_FUSESTATE": [
        "保险丝使能",
        "保险丝状态"
    ],
    "PC_SET_FUSESTATE": [
        "保险丝使能",
        "保险丝状态"
    ],
    "PC_GET_CLUSTER_SBS": [
        "品牌", "当前倍率",
        "电池模块容量",
        "集群容量",
        "总电池数量", "通信失败次数",
        "BMS失败次数", "电芯失败次数",
        "充电MOS关次数", "放电MOS关次数",
        "系统最高电芯温度", "系统最低电芯温度",
        "系统最高电芯电压", "系统最低电芯电压",
        "系统最高电池电压", "系统最低电池电压",
        "系统最大电流", "系统最小电流",
        "系统最高SOC", "系统最低SOC",
        "系统最高SOH", "系统最低SOH",
        "集群充电电压限制", "集群放电电压限制",
        "集群充电电流限制", "集群放电电流限制",
        "集群温度",
        "集群电压(V)",
        "集群电流(A)",
        "集群SOC", "集群SOH",
        "集群保护状态", "集群故障状态",
        "集群循环次数",
        *[f"保留{i+1}" for i in range(10)]
    ]
}

STRUCT_COMMANDS = {
    "NONE": 0x00,
    "PC_LOGIN": 0x01,
    "PC_LOGOUT": 0x02,
    "PC_GET_OLDSBS": 0x03,
    "PC_GET_SBS": 0x13,
    "PC_GET_ADC": 0x04,
    "PC_GET_IO": 0x05,
    "PC_GET_OLDVER": 0x06,
    "PC_GET_VER": 0x16,
    "PC_GET_KB": 0x07,
    "PC_SET_KB": 0x08,
    "PC_SET_BMS": 0x09,
    "PC_GET_BMS": 0x15,
    "PC_OPEN_CHG": 0x0A,
    "PC_CLOSE_CHG": 0x0B,
    "PC_OPEN_DIS": 0x0C,
    "PC_CLOSE_DIS": 0x0D,
    "PC_GET_SERIALNUM": 0x10,
    "PC_SET_SERIALNUM": 0x11,
    "PC_A_PRINT": 0x14,
    "PC_SET_HEATERMODE": 0x17,
    "PC_SET_FORCEDDISMODE": 0x18,
    "PC_SET_PWSFUNCTION": 0x19,
    "PC_SET_SYSTIME": 0x20,
    "PC_GET_SYSTIME": 0x29,
    "PC_Buzzer_ON": 0x23,
    "PC_Buzzer_OFF": 0x24,
    "PC_GET_OCP_DELAYTIME": 0x25,
    "PC_SET_OCP_DELAYTIME": 0x26,
    "PC_OPEN_CHGLIMIT": 0x27,
    "PC_CLOSE_CHGLIMIT": 0x28,
    "PC_GET_CLUSTER_SBS": 0x30,
    "PC_SET_RT0_EN": 0x31,
    "PC_SET_RT1_EN": 0x32,
    "PC_SET_RT2_EN": 0x33,
    "PC_SET_RT0_OFF": 0x34,
    "PC_SET_RT1_OFF": 0x35,
    "PC_SET_RT2_OFF": 0x36,
    "PC_SET_LIFE_PARA": 0x40,
    "PC_GET_LIFE_PARA": 0x41,
    "PC_SET_CELL_CAP_PARA": 0x42,
    "PC_GET_CELL_CAP_PARA": 0x43,
    "PC_GET_RUN_DATA": 0x44,
    "PC_CLEAR_RUN_DATA": 0x45,
    "PC_SET_WAIT_TIMEOUT": 0x46,
    "PC_FACTORY_CLEAER": 0x47,
    "PC_GET_CLUSTER_STATUS": 0x49,
    "PC_GET_DEBUG_DATA": 0x4C,
    "PC_GET_CLUSTER_MINRCD": 0x50,
    "PC_CLEAR_CLUSTER_MINRCD": 0x51,
    "PC_GET_SELF_MINRCD": 0x54,
    "PC_CLEAR_SELF_MINRCD": 0x55,
    "PC_GET_SELF_DAYRCD": 0x56,
    "PC_CLEAR_SELF_DAYRCD": 0x57,
    "PC_GET_SELF_ALMRCD": 0x58,
    "PC_CLEAR_SELF_ALMRCD": 0x59,
    "PC_SET_SHUTDOWN": 0x60,
    "PC_GET_FUSESTATE": 0x61,
    "PC_SET_FUSESTATE": 0x62,
    "PC_SET_BALANCE": 0x63,
    "PC_SET_SLEEP": 0x64,
    "PC_GET_MOSHTDATA": 0x65,
    "PC_SET_MOSHTDATA": 0x66,
    "MCU_A_PRINT": 0x94,
    "PC_GET_INF" : 0x71
}

# 定义需要显示十六进制的变量
HEX_DISPLAY_VARIABLES = {
    "PC_GET_SBS": [
        "其他信息", "告警状态", "保护状态", "失效状态", "均衡状态"
    ],
    "PC_GET_BMS": [
        # 可以根据需要添加其他命令的十六进制显示变量
    ],
    "PC_GET_MOSHTDATA": [
        "MOS温度告警", "MOS温度告警恢复", "MOS温度保护", "MOS温度保护恢复"
    ],
    "PC_GET_CLUSTER_SBS": [
        "集群保护状态", "集群故障状态"
    ]
}

# 将所有字典组合成一个字典
config_data = {
    "STRUCT_FORMATS": STRUCT_FORMATS,
    "STRUCT_ADDRESSES": STRUCT_ADDRESSES,
    "STRUCT_VARIABLES": STRUCT_VARIABLES,
    "STRUCT_COMMANDS": STRUCT_COMMANDS,
    "HEX_DISPLAY_VARIABLES": HEX_DISPLAY_VARIABLES
}

# 写入读出对应关系管理
WRITE_READ_COMMAND_MAPPING = {
    # 写入命令 : 读取命令
    "PC_SET_KB": "PC_GET_KB",
    "PC_SET_BMS": "PC_GET_BMS",
    "PC_SET_OCP_DELAYTIME": "PC_GET_OCP_DELAYTIME",
    "PC_SET_CELL_CAP_PARA": "PC_GET_CELL_CAP_PARA",
    "PC_SET_LIFE_PARA": "PC_GET_LIFE_PARA",
    "PC_SET_MOSHTDATA": "PC_GET_MOSHTDATA",
    "PC_SET_SERIALNUM": "PC_GET_SERIALNUM",
    "PC_SET_FUSESTATE": "PC_GET_FUSESTATE",
}

# 读取写入对应关系管理（反向映射）
READ_WRITE_COMMAND_MAPPING = {
    # 读取命令 : 写入命令
    "PC_GET_KB": "PC_SET_KB",
    "PC_GET_BMS": "PC_SET_BMS",
    "PC_GET_OCP_DELAYTIME": "PC_SET_OCP_DELAYTIME",
    "PC_GET_CELL_CAP_PARA": "PC_SET_CELL_CAP_PARA",
    "PC_GET_LIFE_PARA": "PC_SET_LIFE_PARA",
    "PC_GET_MOSHTDATA": "PC_SET_MOSHTDATA",
    "PC_GET_SERIALNUM": "PC_SET_SERIALNUM",
    "PC_GET_FUSESTATE": "PC_SET_FUSESTATE",
}

def get_write_command_from_read(read_command_name):
    """
    根据读取命令名称获取对应的写入命令名称

    Args:
        read_command_name (str): 读取命令名称，如 "PC_GET_LIFE_PARA"

    Returns:
        str: 对应的写入命令名称，如 "PC_SET_LIFE_PARA"，如果没有找到则返回 None
    """
    return READ_WRITE_COMMAND_MAPPING.get(read_command_name, None)

def get_read_command_from_write(write_command_name):
    """
    根据写入命令名称获取对应的读取命令名称

    Args:
        write_command_name (str): 写入命令名称，如 "PC_SET_LIFE_PARA"

    Returns:
        str: 对应的读取命令名称，如 "PC_GET_LIFE_PARA"，如果没有找到则返回 None
    """
    return WRITE_READ_COMMAND_MAPPING.get(write_command_name, None)

def get_write_command_code(read_command_name):
    """
    根据读取命令名称获取对应的写入命令代码

    Args:
        read_command_name (str): 读取命令名称，如 "PC_GET_LIFE_PARA"

    Returns:
        int: 对应的写入命令代码，如 0x40，如果没有找到则返回 None
    """
    write_command_name = get_write_command_from_read(read_command_name)
    if write_command_name and write_command_name in STRUCT_COMMANDS:
        return STRUCT_COMMANDS[write_command_name]
    return None

def get_read_command_code(write_command_name):
    """
    根据写入命令名称获取对应的读取命令代码

    Args:
        write_command_name (str): 写入命令名称，如 "PC_SET_LIFE_PARA"

    Returns:
        int: 对应的读取命令代码，如 0x41，如果没有找到则返回 None
    """
    read_command_name = get_read_command_from_write(write_command_name)
    if read_command_name and read_command_name in STRUCT_COMMANDS:
        return STRUCT_COMMANDS[read_command_name]
    return None

def can_command_be_written(read_command_name):
    """
    检查某个读取命令是否有对应的写入命令

    Args:
        read_command_name (str): 读取命令名称

    Returns:
        bool: 如果有对应的写入命令返回 True，否则返回 False
    """
    return read_command_name in READ_WRITE_COMMAND_MAPPING

def get_all_writable_commands():
    """
    获取所有可写入的命令对应关系

    Returns:
        dict: 所有可写入的命令对应关系字典
    """
    return READ_WRITE_COMMAND_MAPPING.copy()

def get_all_display_windows():
    """
    获取所有可显示的窗口配置（自动生成）
    
    Returns:
        list: 窗口配置列表，每项格式：
            {
                'window_id': str,        # 窗口ID（命令名称）
                'title': str,            # 窗口标题
                'column_mode': int,      # 列模式：2=只读，3=可读写
                'default_visible': bool, # 是否默认显示
                'cmd_code': int,        # 命令码
                'expected_row_count': int # 预期数据行数
            }
    """
    windows = []
    
    # 遍历所有有格式定义的结构体
    for struct_name in STRUCT_FORMATS.keys():
        # 只为 PC_GET_* 命令生成窗口
        if not struct_name.startswith('PC_GET_'):
            continue
        
        # 判断是否可写（在 READ_WRITE_COMMAND_MAPPING 中）
        is_writable = struct_name in READ_WRITE_COMMAND_MAPPING
        column_mode = 3 if is_writable else 2
        
        # 自动生成标题（去掉 PC_GET_ 前缀）
        display_name = struct_name.replace('PC_GET_', '')
        
        # 根据名称添加图标和中文描述
        title_map = {
            'SBS': '📊 SBS数据',
            'BMS': '⚙️ BMS参数',
            'KB': '📐 校准参数',
            'OCP_DELAYTIME': '⏱️ 过流延时',
            'CELL_CAP_PARA': '🔋 电芯容量',
            'MOSHTDATA': '🌡️ MOS温度',
            'LIFE_PARA': '📅 生命周期',
            'VER': '📋 版本信息',
            'INF': 'ℹ️ 系统信息',
            'SERIALNUM': '🔢 序列号',
            'FUSESTATE': '🔌 保险丝信息',
            'CLUSTER_SBS': '🔗 并机信息',
        }
        
        title = title_map.get(display_name, f'📄 {display_name}')
        
        # 获取命令码
        cmd_code = STRUCT_COMMANDS.get(struct_name, 0)
        
        # 默认显示规则：电芯容量、SBS数据、版本信息默认显示
        default_visible = struct_name in ['PC_GET_KB', 'PC_GET_SBS', 'PC_GET_VER']
        
        # 获取预期的数据行数（从 STRUCT_VARIABLES 中获取变量数量）
        expected_row_count = len(STRUCT_VARIABLES.get(struct_name, []))
        
        windows.append({
            'window_id': struct_name,
            'title': title,
            'column_mode': column_mode,
            'default_visible': default_visible,
            'cmd_code': cmd_code,
            'expected_row_count': expected_row_count
        })
    
    # 添加告警-保护信息窗口
    # 告警和保护最多各32位，按位对应，所以最多32行
    windows.append({
        'window_id': 'ALARM_PROTECT',
        'title': '⚠️ 告警-保护信息',
        'column_mode': 2,
        'default_visible': True,
        'cmd_code': 0,
        'expected_row_count': 32,
        'window_type': 'alarm_protect'
    })
    
    # 添加其他状态信息窗口
    # 错误、信息、均衡各一列，找最大行数
    windows.append({
        'window_id': 'OTHER_STATUS',
        'title': 'ℹ️ 其他状态信息',
        'column_mode': 2,
        'default_visible': True,
        'cmd_code': 0,
        'expected_row_count': 21,  # info有21个状态位，是最多的
        'window_type': 'other_status'
    })
    
    # 添加电池状态窗口
    windows.append({
        'window_id': 'BATTERY_STATUS',
        'title': '🔋 电池状态',
        'column_mode': 2,
        'default_visible': True,
        'cmd_code': 0,
        'expected_row_count': 1,
        'window_type': 'battery_status'
    })
    
    return windows

def get_window_column_mode(struct_name):
    """
    获取指定结构体的列模式
    
    Args:
        struct_name: 结构体名称（如 'PC_GET_SBS'）
        
    Returns:
        int: 2=只读（两列），3=可读写（三列）
    """
    return 3 if struct_name in READ_WRITE_COMMAND_MAPPING else 2

# 更新配置数据，包含写入读出对应关系
config_data.update({
    "WRITE_READ_COMMAND_MAPPING": WRITE_READ_COMMAND_MAPPING,
    "READ_WRITE_COMMAND_MAPPING": READ_WRITE_COMMAND_MAPPING
})

class HexParserApp(QMainWindow):
    decode_data_ok_signal = pyqtSignal(int,dict)

    def __init__(self):
        super().__init__()
        self.initUI()
        # self.set_config_file()  # 已禁用配置文件读写
        self.struct_name_list = []
    def update_dict(self, target, source):
        """递归更新字典"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target:
                self.update_dict(target[key], value)
            else:
                target[key] = value
    def set_config_file(self, force_write=False):
        """
        设置配置文件（已禁用，保留代码供将来使用）

        Args:
            force_write (bool): 如果为 True，强制写入当前 config_data，不从文件读取
        """
        # 已禁用配置文件读写功能，直接返回
        return
        
        # ====== 以下代码已禁用，保留供将来使用 ======
        # # 配置文件路径
        # config_file_path = os.path.join(os.getcwd(), "default_config.json")

        # # 如果不是强制写入，则先读取现有配置并合并
        # if not force_write:
        #     # 检查配置文件是否存在
        #     if os.path.exists(config_file_path):
        #         try:
        #             # 读取现有配置文件
        #             with open(config_file_path, 'r', encoding='utf-8') as config_file:
        #                 existing_config = json.load(config_file)

        #             # 检查现有配置文件格式是否正确
        #             if isinstance(existing_config, dict):
        #                 # 比较现有配置文件与当前配置数据
        #                 if existing_config != config_data:
        #                     # 更新 config_data 为现有配置文件内容
        #                     self.update_dict(config_data, existing_config)
        #                     print("已从现有配置文件加载配置")
        #                 else:
        #                     print("配置文件已存在且内容相同，无需更新")
        #                     return  # 内容相同，不需要写入
        #             else:
        #                 print("配置文件格式不正确，使用当前配置数据")
        #         except Exception as e:
        #             traceback.print_exc()
        #             print(f"读取配置文件失败: {e}")
        #     else:
        #         print("配置文件不存在，将创建新文件")

        # # 将字典写入 JSON 文件
        # try:
        #     with open(config_file_path, 'w', encoding='utf-8') as config_file:
        #         json.dump(config_data, config_file, ensure_ascii=False, indent=4)
        #     print(f"配置文件已生成或更新: {config_file_path}")
        # except Exception as e:
        #     traceback.print_exc()
        #     print(f"写入配置文件失败: {e}")
    def initUI(self):
        self.setWindowTitle("HEX 文件解析器")
        self.setGeometry(100, 100, 800, 600)

        # 创建主布局
        layout = QVBoxLayout()

        # 创建文本框用于显示结果
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily("Courier New")  # 使用等宽字体
        layout.addWidget(self.text_edit)

        # 创建按钮用于加载 HEX 文件
        self.load_button = QPushButton("加载 HEX 文件")
        self.load_button.clicked.connect(self.load_hex_file)
        layout.addWidget(self.load_button)

        # 设置主窗口的中心部件
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def set_struct_to_cell_16(self):
        """
        设置为16串配置
        - PC_GET_SBS: 16个电池单元 + 5个温度传感器
        - PC_GET_KB: 16个电池单元 + 8个温度传感器
        """
        # PC_GET_SBS: 5个温度传感器
        STRUCT_FORMATS["PC_GET_SBS"] = "<LL" + \
        "HHHHHHHHHHHHHHHH" +\
        "l" +\
        "hhhhh" +\
        "HHH" +\
        "LLLLL" +\
        "HH" +\
        "LLL"
        STRUCT_VARIABLES["PC_GET_SBS"] = ["PACK电压", "BATT电压",
        *[f"第【{i+1}】节电压" for i in range(16)],
        "电流",
        *[f"环境温度{i+1}" for i in range(5)],
        "剩余容量", "满充容量", "设计容量",
        "其他信息", "告警状态", "保护状态", "失效状态", "均衡状态",
        "电池状态", "SOC",
        "容量保持率", "放电次数", "总放电容量"]

        # PC_GET_KB: 8个温度传感器
        STRUCT_FORMATS["PC_GET_KB"] = "<HH" + \
        "HHHHHHHHHHHHHHHH" +\
        "HhHhHhHhHhHh" +\
        "HHHHHHHH"
        STRUCT_VARIABLES["PC_GET_KB"] = ["Pack电压K", "Batt电压K",
        *[f"第【{i+1}】节电压K" for i in range(16)],
        "50-500安K(注，不同电池，电流范围不同，谨慎参考)",    "50-500安B",
        "-(50-500)安K", "-(50-500)安B",
        "10-50安SK",    "10-50安SB",
        "-10-50安SK",   "-10-50安SB",
        "0-10安SSK",    "0-10安SSB",
        "-(0-10)安SSK", "-(0-10)安SSB",
        *[f"温度{i+1}K" for i in range(8)]]

        # 修改完成后，更新 config_data 字典
        config_data["STRUCT_FORMATS"] = STRUCT_FORMATS
        config_data["STRUCT_VARIABLES"] = STRUCT_VARIABLES

        # 强制写入配置文件（已禁用）
        print("16串配置已更新（SBS:5个温度, KB:8个温度）")
        # self.set_config_file(force_write=True)  # 已禁用配置文件写入

    def set_struct_to_cell_32(self):
        """
        设置为32串配置
        - PC_GET_SBS: 32个电池单元 + 13个温度传感器
        - PC_GET_KB: 32个电池单元 + 16个温度传感器
        """
        # PC_GET_SBS: 13个温度传感器（根据C结构体：TSBS）
        STRUCT_FORMATS["PC_GET_SBS"] = "<LL" + \
        "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH" +\
        "l" +\
        "hhhhhhhhhhhhh" +\
        "HHH" +\
        "LLLLL" +\
        "HH" +\
        "LLL"
        STRUCT_VARIABLES["PC_GET_SBS"] =  ["PACK电压", "BATT电压",
        *[f"第【{i+1}】节电压" for i in range(32)],
        "电流",
        *[f"环境温度{i+1}" for i in range(13)],
        "剩余容量", "满充容量", "设计容量",
        "其他信息", "告警状态", "保护状态", "失效状态", "均衡状态",
        "电池状态", "SOC",
        "容量保持率", "放电次数", "总放电容量"]

        # PC_GET_KB: 16个温度传感器（根据C结构体：TKB）
        STRUCT_FORMATS["PC_GET_KB"] = "<HH" + \
        "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH" +\
        "HhHhHhHhHhHh" +\
        "HHHHHHHHHHHHHHHH"
        STRUCT_VARIABLES["PC_GET_KB"] = ["Pack电压K", "Batt电压K",
        *[f"第【{i+1}】节电压K" for i in range(32)],
        "50-500安K(注，不同电池，电流范围不同，谨慎参考)",     "50-500安B",
        "-(50-500)安K",  "-(50-500)安B",
        "10-50安SK",   "10-50安SB",
        "-10-50安SK",  "-10-50安SB",
        "0-10安SSK",     "0-10安SSB",
        "-(0-10)安SSK", "-(0-10)安SSB",
        *[f"温度{i+1}K" for i in range(16)]]

        # 修改完成后，更新 config_data 字典
        config_data["STRUCT_FORMATS"] = STRUCT_FORMATS
        config_data["STRUCT_VARIABLES"] = STRUCT_VARIABLES

        # 强制写入配置文件（已禁用）
        print("32串配置已更新")
        # self.set_config_file(force_write=True)  # 已禁用配置文件写入
    def get_struct_name_list(self):
        for key, value in STRUCT_VARIABLES.items():
            struct_str = key
            for i in value:
                struct_str += "," + i
            self.struct_name_list.append(struct_str)
        return self.struct_name_list

    def get_current_cell_config(self):
        """
        检测当前配置是16串还是32串

        Returns:
            int: 返回电芯数量，16 或 32，如果无法确定则返回 -1
        """
        try:
            # 通过检查 PC_GET_SBS 的 usCellV 数量来判断
            # 16串配置: usCellV[0] ~ usCellV[15]，共16个
            # 32串配置: usCellV[0] ~ usCellV[31]，共32个

            sbs_variables = STRUCT_VARIABLES.get("PC_GET_SBS", [])

            # 计算 usCellV 的数量
            cell_count = sum(1 for var in sbs_variables if var.startswith("usCellV["))

            if cell_count == 16:
                return 16
            elif cell_count == 32:
                return 32
            else:
                LogManager.get_instance().write_log(f"警告：未知的电芯数量 {cell_count}")
                return -1

        except Exception as e:
            LogManager.get_instance().write_log(f"检测配置失败: {str(e)}")
            traceback.print_exc()
            return -1

    def load_hex_file(self):
        # 打开文件对话框选择 HEX 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "打开 HEX 文件", "", "(*.*);;HEX 文件 (*.hex)")
        if not file_path:
            return

        # 使用 intelhex 库加载 HEX 文件
        try:
            ih = IntelHex(file_path)
        except Exception as e:
            self.text_edit.append(f"加载 HEX 文件失败：{e}")
            return

        # 解析结构体数据
        parsed_data = self.parse_hex_data(ih)

        # 显示解析结果
        self.text_edit.clear()
        for struct_name, data in parsed_data.items():
            self.text_edit.append(f"\n==== {struct_name} @ {STRUCT_ADDRESSES[struct_name]:#08x} ====")
            self.text_edit.append("-" * 70)
            self.text_edit.append(f"{'变量名':<25} | {'原始字节':<20} | {'十进制值':<15}")
            self.text_edit.append("-" * 70)
            for var_name, hex_bytes, dec_val in data:
                self.text_edit.append(f"{var_name:<25} | {hex_bytes:<20} | {dec_val:<15}")
            self.text_edit.append("\n")
    def parse_hex_data(self, ih):
        """
        严格按字节解析的增强版本
        """
        parsed_data = {}
        for struct_name, address in STRUCT_ADDRESSES.items():
            fmt = STRUCT_FORMATS[struct_name]
            size = struct.calcsize(fmt)

            try:
                # 读取原始字节
                data_bytes = ih.tobinstr(start=address, size=size)
                # 解析为元组
                values = struct.unpack(fmt, data_bytes)
                # 转换为十六进制字符串
                hex_values = [f"0x{b:02X}" for b in data_bytes]
                hex_byte_array = []

                # 处理有符号值
                dec_values = []
                for i, (var_name, value) in enumerate(zip(STRUCT_VARIABLES[struct_name], values)):
                    # 根据格式字符判断符号
                    fmt_char = fmt[1:][i]  # 跳过字节序字符
                    byte_len = struct.calcsize(fmt_char)
                    if byte_len == 1:
                        hex_byte_array.append(f"0x{value:02X}")
                    elif byte_len == 2:
                        hex_byte_array.append(f"0x{value:04X}")
                    elif byte_len == 4:
                        hex_byte_array.append(f"0x{value:08X}")
                        pass
                    if fmt_char in ('h', 'l'):
                        dec_values.append(str(value))  # 保留符号
                    else:
                        dec_values.append(str(value & 0xFFFF_FFFF))  # 无符号显示

                # 按字节对齐显示
                display_data = []
                byte_offset = 0
                i = 0
                for var_name, dec_val in zip(STRUCT_VARIABLES[struct_name], dec_values):
                    byte_len = struct.calcsize(fmt[1:][i])  # 计算变量字节长度
                    display_data.append((
                        var_name,
                        ''.join(hex_byte_array[i]),
                        dec_val
                    ))
                    byte_offset += byte_len
                    i += 1
                parsed_data[struct_name] = display_data

            except Exception as e:
                self.text_edit.append(f"解析 {struct_name} 失败: {str(e)}")

        return parsed_data
    def decode_cmd_hex_data(self, cmd:int, data_bytes:bytes):
        """
        把二进制数据转换成字典数据
        """
        parsed_data = {}
        if cmd in STRUCT_COMMANDS.values():
            for key, value in STRUCT_COMMANDS.items():
                if value == cmd:
                    struct_name = key
                    break
        else:
            LogManager.get_instance().write_log(f"解析 {cmd:02X} 失败: 无当前命令")
            return "no_cmd", None
        
        # PC_A_PRINT 和 MCU_A_PRINT 指令在 enhanced_main_window.py 中已提前处理
        # 这里不会执行到，保持代码简洁
        
        if struct_name not in STRUCT_FORMATS:
            LogManager.get_instance().write_log(f"解析 {struct_name} 失败: 这个命令没有预存格式细节")
            return struct_name, None
        try:
            fmt = STRUCT_FORMATS[struct_name]
            size = struct.calcsize(fmt)
            if size != len(data_bytes):
                LogManager.get_instance().write_log(f"解析 {struct_name} 失败: 数据长度不匹配, 目标长度: {size}, 实际长度: {len(data_bytes)}")
                return None, None

            # 解析为元组
            values = struct.unpack(fmt, data_bytes)
            
            # 解析格式字符串，获取每个字段的格式字符
            fmt_chars = re.findall(r'(\d*)([a-zA-Z])', fmt[1:])  # 跳过字节序标记
            field_formats = []
            for count_str, char in fmt_chars:
                count = int(count_str) if count_str else 1
                if char == 's':
                    field_formats.append(char)
                else:
                    field_formats.extend([char] * count)

            # 处理有符号值
            dec_values = []
            hex_byte_array = []

            for i, (var_name, value) in enumerate(zip(STRUCT_VARIABLES[struct_name], values)):
                # 获取对应的格式字符
                fmt_char = field_formats[i] if i < len(field_formats) else 'L'
                
                # 处理字符串字段（bytes类型）
                if isinstance(value, bytes):
                    # 字节串类型，解码为字符串
                    # 对于序列号等字段，过滤掉填充字节(0xFF)和控制字符
                    # 只保留可打印的ASCII字符（0x20-0x7E）
                    filtered_bytes = bytes([b for b in value if 0x20 <= b <= 0x7E])
                    try:
                        # 尝试用ASCII解码（序列号通常是ASCII字符）
                        str_value = filtered_bytes.decode('ascii', errors='ignore')
                    except:
                        # 如果失败，用latin-1解码
                        str_value = filtered_bytes.decode('latin-1', errors='ignore')
                    dec_values.append(str_value)
                    hex_bytes = ''.join([f"{b:02X}" for b in value])
                    hex_byte_array.append(hex_bytes)
                elif isinstance(value, int):
                    # 处理数值字段
                    if value < 256:
                        hex_byte_array.append(f"0x{value:02X}")
                    elif value < 65536:
                        hex_byte_array.append(f"0x{value:04X}")
                    else:
                        hex_byte_array.append(f"0x{value:08X}")

                    # 检查是否需要显示十六进制格式
                    hex_vars = HEX_DISPLAY_VARIABLES.get(struct_name, [])
                    if var_name in hex_vars:
                        # 为指定变量只显示十六进制字符串
                        if value < 256:
                            hex_str = f"0x{value:02X}"
                        elif value < 65536:
                            hex_str = f"0x{value:04X}"
                        else:
                            hex_str = f"0x{value:08X}"
                        dec_values.append(hex_str)  # 只显示十六进制
                    else:
                        # 根据格式字符判断是否有符号（小写=有符号，大写=无符号）
                        if fmt_char in ('b', 'h', 'l', 'q'):  # 有符号格式
                            dec_values.append(str(value))  # 保留符号
                        else:  # 无符号格式 ('B', 'H', 'L', 'Q')
                            dec_values.append(str(value & 0xFFFF_FFFF))  # 无符号显示
                else:
                    # 其他类型的值
                    hex_byte_array.append(str(value))
                    dec_values.append(str(value))

            # 按字节对齐显示
            display_data = []
            for i, (var_name, dec_val) in enumerate(zip(STRUCT_VARIABLES[struct_name], dec_values)):
                display_data.append((
                    var_name,
                    hex_byte_array[i],
                    dec_val
                ))
            parsed_data[struct_name] = display_data

        except Exception as e:
            traceback.print_exc()
            LogManager.get_instance().write_log(f"解析 {struct_name} 失败: {str(e)}")

        return struct_name, parsed_data



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HexParserApp()
    str1 = "4A 9A 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 15 00 16 00 16 00 00 00 00 00 00 00 00 00 00 00 00 00 64 00 10 27 00 00 C0 00 01 00 20 10 00 00 00 00 00 00 10 00 00 00 00 00 00 00 00 00 01 00 64 00 00 00 00 00 00 00 00 00 00 00"
    # 转换成字节数据
    str1_bytes = bytearray.fromhex(str1.replace(" ", ""))
    # 测试数据

    test_data = bytearray([
        0x01, 0x00, 0x02, 0x00, 0x03, 0x00, 0xE7, 0x07, 0x0A, 0x0F, 0x00,0x00, # bootVer
        0x04, 0x00, 0x05, 0x00, 0x06, 0x00, 0xE7, 0x07, 0x0B, 0x14, 0x00,0x00, # app_Ver
        0x07, 0x00, 0x08, 0x00, 0x09, 0x00, 0xE7, 0x07, 0x0C, 0x19, 0x00,0x00, # buffVer
        0x0A, 0x00, 0x0B, 0x00, 0x0C, 0x00, 0xE8, 0x07, 0x01, 0x01, 0x00,0x00, # backVer
        0x49, 0x43, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38,  # icName
        0x39, 0x30, 0x31, 0x32, 0x33,  # icName (continued)
        0x01,  # writableArea
        0x78, 0x56, 0x34, 0x12,  # pcAddr
        0xD0, 0x34, 0x56, 0x78  # uniqueID
    ])

    # 解析测试数据
    struct_name, parsed_data = window.decode_cmd_hex_data(0x13, str1_bytes)
    print(f"Struct Name: {struct_name}")
    print("Parsed Data:")
    for var_name, hex_val, dec_val in parsed_data["PC_GET_SBS"]:
        print(f"{var_name}: {hex_val} | {dec_val}")

    window.show()
    sys.exit(app.exec())
