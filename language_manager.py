"""
统一语言管理模块
支持多语言切换，集中管理所有翻译文本
支持中文、英文及其他语言扩展
"""
import os

class LanguageManager:
    """语言管理器 - 单例模式"""
    
    _instance = None
    
    # 所有翻译数据
    TRANSLATIONS = {
        'zh_CN': {
            # ========== UI文本（enhanced_main_window.py + newblue3_17.py） ==========
            'ui': {
                'window_title': '增强版BMS调试工具 - 多窗口管理',
                'user_app_title': '安培电池系统软件',
                'control_panel': 'BMS调试工具控制面板',
                'factory_mode': '🏭 工厂模式',
                'simplified_window': '📱 简化窗口',
                'cell_32_config': '⚡ 32电芯配置',
                'cell_32_tooltip': '勾选：32电芯+15温度传感器\n不勾选：16电芯+SBS 5温度+KB 8温度',
                'open_connection': '打开连接窗口',
                'disconnect': '🔌 断开连接',
                'start_monitor': '▶️ 开始监控',
                'stop_monitor': '⏸️ 停止监控',
                'query_version': '📋 查询版本',
                'clear_queue': '🗑️ 清空队列',
                'select_all': '全选',
                'deselect_all': '全不选',
                'read_all': '📖 读取所有',
                'read': '🔄 读取',
                'write': '✏️ 写入',
                'window_control_title': '数据窗口控制',
                'data_display_title': '数据显示窗口',
                'status_disconnected': '⭕ 断开',
                'status_bluetooth': '🔗 蓝牙已连接',
                'status_serial': '🔗 串口已连接',
                'send_queue': '📤 发送队列',
                'receive': '📥 接收',
                'send': '📤 发送',
                'log_init': '增强版主窗口初始化',
                'log_factory_mode': '切换到工厂模式',
                'log_user_mode': '切换到用户模式',
                'log_cell_config': '切换电芯配置',
                'log_16cell': '16电芯+SBS 5温度+KB 8温度',
                'log_32cell': '32电芯+15温度',
                'log_loaded_config': '已加载电芯配置',
                'log_queue_cleared': '已清空发送队列',
                'log_monitoring_start': '开始监控',
                'log_monitoring_start': '开始监控',
                'log_monitoring_stop': '停止监控',
                # newblue3_17.py 窗口标题和UI元素
                'bt_tool_title': 'firstuse - 蓝牙调试工具',
                'bt_tool_simplified_title': '蓝牙/串口连接',
                'startup_app': '正在启动应用...',
                # Tab标签
                'tab_connection': '连接',
                'tab_control': '控制',
                'tab_advanced': '高级',
                'tab_test': '测试',
                # 自动连接
                'auto_connect_group': '自动连接',
                'auto_connect_enable': '启用',
                'device_name_label': '名称:',
                'device_name_placeholder': '设备名称',
                'mac_address_label': 'MAC:',
                'mac_address_placeholder': 'MAC地址(可选)',
                'interval_label': '间隔:',
                'interval_seconds': '秒',
                # 蓝牙连接
                'bt_connection_group': '蓝牙连接',
                'device_list_label': '设备列表:',
                'rssi_threshold': 'RSSI >',
                'btn_connect': '连接',
                'btn_disconnect': '断开',
                'btn_connecting': '正在连接...',
                'status_connected': '🔗 已连接',
                'status_connecting': '🔄 正在连接...',
                # 串口连接
                'serial_connection_group': '串口连接',
                'serial_port_label': '串口:',
                'baud_rate_label': '波特率:',
                'data_bits_label': '数据位:',
                'stop_bits_label': '停止位:',
                'parity_label': '校验位:',
                'parity_none': '无',
                'parity_odd': '奇校验',
                'parity_even': '偶校验',
                'btn_connect_serial': '连接串口',
                'btn_disconnect_serial': '断开串口',
                'monitor_interval_label': '监控间隔:',
                # 扫描按钮
                'btn_scan_refresh': '🔍 扫描并刷新',
                # MOS控制
                'mos_control_group': 'MOS控制',
                'btn_charge_on': '充电开',
                'btn_charge_off': '充电关',
                'btn_discharge_on': '放电开',
                'btn_discharge_off': '放电关',
                # 保电控制
                'store_power_group': '保电控制',
                'btn_store_power_on': '保电开',
                'btn_store_power_off': '保电关',
                # 加热模式
                'heating_mode_group': '加热模式',
                'btn_self_heating': '自加热',
                'btn_charger_heating': '充电器加热',
                # RT控制
                'rt_control_group': 'RT控制',
                'btn_rt0_on': 'RT0开',
                'btn_rt1_on': 'RT1开',
                'btn_rt2_on': 'RT2开',
                'btn_rt0_off': 'RT0关',
                'btn_rt1_off': 'RT1关',
                'btn_rt2_off': 'RT2关',
                # 其他控制
                'other_control_group': '其他控制',
                'btn_shutdown': '🔌 设备关机',
                'bt_name_label': '名称:',
                'bt_name_placeholder': '输入新蓝牙名称',
                'btn_change_bt_name': '修改蓝牙名称',
                # HEX文件和烧录
                'hex_file_group': 'HEX文件',
                'btn_select_hex': '选择HEX文件',
                'hex_file_not_selected': '未选择文件',
                'hex_file_size': '大小: {0} 字节',
                'hex_file_parse_failed': '❌ 文件解析失败',
                'cell_32_config_checkbox': '32电芯配置',
                # 密码管理
                'password_group': '密码管理',
                'password_label': '密码:',
                'password_placeholder': '6位密码',
                'btn_query_lock': '查询',
                'btn_login': '验证',
                'btn_set_password': '设置',
                'btn_reset_password': '取消',
                # 烧录控制
                'programming_group': '烧录控制',
                'btn_start_programming': '开始烧录',
                'btn_stop_programming': '再点击即停止',
                'packet_progress': '包号: {0} / {1}',
                'btn_batch_program': '批量烧录',
                'btn_stop_batch': '再点击即停止',
                'batch_success_count': '成功: {0}',
                'batch_total_count': '总数: {0} 成功数: {1}',
                # 测试功能
                'send_test_group': '发送测试',
                'send_input_label': '输入:',
                'send_input_placeholder': '发送数据',
                'checkbox_hex': 'HEX',
                'checkbox_crlf': '\\r\\n',
                'btn_send': '发送',
                'btn_register': '注册',
                'btn_connection_test': '连接测试',
                # 连续发送
                'continuous_send_group': '连续发送',
                'interval1_label': '间隔1:',
                'interval2_label': '间隔2:',
                'btn_start_continuous': '开始连续发送',
                'no_ack_count': '无回应={0}',
                'err_ack_count': 'ack错误={0}',
                'total_send_count': '总次数={0}',
                # 接收数据
                'receive_data_label': '接收数据:',
                'checkbox_hex_display': 'HEX显示',
                'btn_clear_receive': '清空',
                # 加热模式控制
                'heating_mode_title': '加热模式',
                # 充放电控制
                'charge_discharge_control': '充放电控制',
                # 简化窗口标题
                'simplified_bt_title': '蓝牙连接',
                'simplified_serial_title': '串口连接',
                'simplified_auto_connect': '自动连接',
                'auto_save_hint': '💡 自动保存',
                # 动态状态文本
                'scanning_devices': '正在扫描设备...',
                'bt_adapter_not_ready': '蓝牙适配器未就绪，请检查系统蓝牙设置',
                'devices_found': '发现的蓝牙设备:',
                'handshake_start': '开始握手',
                'handshake_success': '握手成功',
                'erase_success': '擦除成功',
                'start_batch_100': '开始烧录100',
                # 版本和公司信息
                'company_info': '深圳安培时代数字新能源科技有限公司 - 电池系统软件 v{0}',
                'version_info_title': '版本信息:',
                'build_date': '打包日期',
                'git_branch': 'Git分支',
                'git_commit': 'Commit',
                'commit_message': '提交信息',
                'commit_author': '提交作者',
                'commit_time': '提交时间',
                'version_number': '版本号: v{0}',
                'version_read_error': '读取版本信息出错: {0}',
                # 设备连接状态
                'unknown_device': '未知设备',
                'unknown_port': '未知串口',
                'bt_connected_with_addr': '🔗 蓝牙已连接 | 📱 {0} | 📍 {1}',
                'bt_connected_no_addr': '🔗 蓝牙已连接 | 📱 {0}',
                'serial_connected': '🔗 串口已连接 | 🔌 {0}',
                # 窗口配置日志
                'log_windows_configured': '✅ 已自动配置 {0} 个显示窗口',
                # 监控和命令相关
                'log_monitoring_error': '监控循环错误: {0}',
                'log_send_command_failed': '发送命令失败: {0}',
                'log_mode_switched': '切换到{0}模式',
                'mode_factory': '工厂',
                'mode_user': '用户',
                'log_cell_config_switch': '切换电芯配置: {0}',
                'config_16cell_name': '16电芯+SBS 5温度+KB 8温度',
                'config_32cell_name': '32电芯+15温度',
                'log_cell_config_loaded': '已加载电芯配置: {0}',
                'log_cell_config_sync_failed': '同步电芯配置失败: {0}',
                # 语言切换
                'lang_name_zh': '简体中文',
                'lang_name_en': 'English',
                'log_language_switched': '界面语言已切换为: {0}',
                'language_switched_title': '语言已切换 / Language Changed',
                'language_switched_message': '界面语言已切换为: {0}\nLanguage switched to: {0}\n\n注意：某些窗口需要重新打开才能完全生效。\nNote: Some windows need to be reopened for full effect.',
                'log_ui_update_error': '更新界面文本时出错: {0}',
                # 数据请求日志
                'log_read_request': '🖱️ 收到手动读取请求: {0}',
                'log_read_command_not_found': '未找到窗口 {0} 对应的读取命令',
                'log_write_request': '收到写入请求: {0}, 修改项数: {1}',
                'log_write_not_supported': '窗口 {0} 不支持写入',
                'log_cannot_get_window_data': '无法获取窗口数据',
                'log_value_convert_failed': '行{0}值转换失败: {1}',
                'log_struct_format_not_found': '未找到结构体格式: {0}',
                'log_pack_failed': '数据打包失败: {0}',
                'log_command_construct_failed': '命令构造失败: {0}',
                'log_write_command_sent': '✅ 写入命令已发送: {0}',
                'log_write_request_failed': '处理写入请求失败: {0}',
                # 数据处理错误
                'log_data_display_mgr_not_init': '错误：data_display_mgr未初始化',
                'log_custom_process_error': 'custom_process_complete_data错误: {0}',
                'log_update_window_data_failed': '更新窗口数据失败: {0}',
                'log_update_bit_flags_failed': '更新状态位窗口失败: {0}',
                'log_close_bt_window_error': '关闭蓝牙窗口时出错: {0}',
                # 程序错误
                'program_error': '程序错误: {0}',
                # 表头翻译
                'table_header_alarm': '告警',
                'table_header_protect': '保护',
                'table_header_value': '值',
                'table_header_fault': '错误',
                'table_header_info': '信息',
                'table_header_balance': '均衡',
                'table_header_param_name': '参数名',
                'table_header_status_value': '状态值',
            },
            
            # ========== 状态位名称（struct_model.py） ==========
            'status_bits': {
                'alarm': {
                    'pack_ov': 'PACK_OV',
                    'batt_ov': 'BATT_OV',
                    'cell_ov': 'CELL_OV',
                    'batt_uv': 'BATT_UV',
                    'cell_uv': 'CELL_UV',
                    'chg_oc': 'CHG_OC',
                    'dis_oc': 'DIS_OC',
                    'chg_ot': 'CHG_OT',
                    'dis_ot': 'DIS_OT',
                    'chg_ut': 'CHG_UT',
                    'dis_ut': 'DIS_UT',
                    'soc_l': 'SOC_L',
                    'end_life': 'END_LIFE',
                    'mos_ht': 'MOS_HT',
                },
                'protect': {
                    'pack_ov': 'PACK_OV',
                    'batt_ov': 'BATT_OV',
                    'cell_ov': 'CELL_OV',
                    'batt_uv': 'BATT_UV',
                    'cell_uv': 'CELL_UV',
                    'chg_oc': 'CHG_OC',
                    'dis_oc': 'DIS_OC',
                    'chg_ot': 'CHG_OT',
                    'dis_ot': 'DIS_OT',
                    'chg_ut': 'CHG_UT',
                    'dis_ut': 'DIS_UT',
                    'short': 'SHORT',
                    'rev': 'REV',
                    'chg_utoc': 'CHG_UTOC',
                    'chg_utov': 'CHG_UTOV',
                    'chg_short': 'CHG_SHORT',
                    'psp': 'PSP',
                    'bq_scd': 'BQ_SCD',
                    'bq_ocd': 'BQ_OCD',
                    'mos_ht': 'MOS_HT',
                    'chg_ut_limit': 'CHG_UT_LIM',
                },
                'fault': {
                    'v_sensor': 'V_SENSOR',
                    't_sensor': 'T_SENSOR',
                    'chg': 'CHG_FAIL',
                    'dis': 'DIS_FAIL',
                    'cell_bad': 'CELL_BAD',
                    'switch_off': 'SW_OFF',
                    'life_end': 'LIFE_END',
                    'bq_uv': 'BQ_UV',
                    'bq_ov': 'BQ_OV',
                    'bq_device': 'BQ_DEV',
                    'bq_overwr': 'BQ_OVRW',
                    'fuse_break': 'FUSE_BRK',
                },
                'info': {
                    'heater_config': 'HEAT_CFG',
                    'heater_on': 'HEAT_ON',
                    'chg_full_t': 'CHG_FULL_T',
                    'batt_full': 'BATT_FULL',
                    'chg_limited_on': 'CHG_LIM_ON',
                    'dis_limited_on': 'DIS_LIM_ON',
                    'chg_mos_off': 'CHG_MOS_OFF',
                    'dis_mos_off': 'DIS_MOS_OFF',
                    'lowvol_limit': 'LOW_V_LIM',
                    'lowtemp_forcechg': 'LOW_T_CHG',
                    'mult_batt': 'MULT_BATT',
                    'can_master': 'CAN_MASTER',
                    'can_slave': 'CAN_SLAVE',
                    'calendar_reach': 'CAL_REACH',
                    'test_kb': 'TEST_KB',
                    'calibrated_v': 'V_CAL',
                    'calibrated_c': 'C_CAL',
                    'lost_canbox': 'CAN_LOST',
                    'no_inv_timeout': 'NO_INV',
                    'fuseen_open': 'FUSE_OPEN',
                    'cell_cto': 'CELL_CTO',
                    'pswfunction_on': 'PSW_ON',
                    'powersave_on': 'PSAVE_ON',
                    'forceddis_on': 'FORCE_DIS',
                    'heatermode_self': 'SELF_HEAT',
                },
                'balance': {
                    'cell': 'C{0}',  # 格式化字符串，{0}会被替换为01-16
                },
                'battery_status': {
                    'idle': 'IDLE',
                    'charging': 'CHG',
                    'discharging': 'DIS',
                    'full': 'FULL',
                }
            },
            
            # ========== 窗口标题 ==========
            'windows': {
                'sbs': '📊 SBS数据',
                'bms': '⚙️ BMS参数',
                'kb': '📐 校准参数',
                'ocp_delay': '⏱️ 过流延时',
                'cell_cap': '🔋 电芯容量',
                'mos_temp': '🌡️ MOS温度',
                'life': '📅 生命周期',
                'version': '📋 版本信息',
                'info': 'ℹ️ 系统信息',
                'serial': '🔢 序列号',
                'fuse': '🔌 保险丝信息',
                'cluster': '🔗 并机信息',
                'alarm_protect': '⚠️ 告警-保护信息',
                'other_status': 'ℹ️ 其他状态信息',
                'battery_status': '🔋 电池状态',
            },
            
            # ========== 变量名模板 ==========
            'var_templates': {
                # SBS变量
                'pack_voltage': 'PACK电压',
                'batt_voltage': 'BATT电压',
                'cell_voltage': '第【{0}】节电压',
                'cell_voltage_k': '第【{0}】节电压K',
                'current': '电流',
                'temp': '环境温度{0}',
                'temp_k': '温度{0}K',
                'remain_cap': '剩余容量',
                'full_cap': '满充容量',
                'design_cap': '设计容量',
                'other_info': '其他信息',
                'alarm_status': '告警状态',
                'protect_status': '保护状态',
                'fault_status': '失效状态',
                'balance_status': '均衡状态',
                'battery_status_label': '电池状态',
                'soc': 'SOC',
                'cap_health': '容量保持率',
                'discharge_count': '放电次数',
                'total_discharge_cap': '总放电容量',
                'reserve': '保留{0}',
                
                # BMS变量
                'chg_power_voltage': '充电功耗电压值',
                'chg_power_diff': '充电功耗Pack与Batt压差',
                'chg_full_start': '充电功满开启电压值',
                'chg_full_stop': '充电功满停止电压值',
                'pack_ov_warn': 'Pack过充-警限值',
                'pack_ov_warn_resume': 'Pack过充-警恢复值',
                'pack_ov_protect': 'Pack过充-保限值',
                'pack_ov_protect_resume': 'Pack过充-保恢复值',
                'batt_ov_warn': 'Batt过充-警限值',
                'batt_ov_warn_resume': 'Batt过充-警恢复值',
                'batt_ov_protect': 'Batt过充-保限值',
                'batt_ov_protect_resume': 'Batt过充-保恢复值',
                'cell_ov_warn': 'Cell过充-警限值',
                'cell_ov_warn_resume': 'Cell过充-警恢复值',
                'cell_ov_protect': 'Cell过充-保限值',
                'cell_ov_protect_resume': 'Cell过充-保恢复值',
                'batt_uv_warn': 'Batt欠压-警限值',
                'batt_uv_warn_resume': 'Batt欠压-警恢复值',
                'batt_uv_protect': 'Batt欠压-保限值',
                'batt_uv_protect_resume': 'Batt欠压-保恢复值',
                'cell_uv_warn': 'Cell欠压-警限值',
                'cell_uv_warn_resume': 'Cell欠压-警恢复值',
                'cell_uv_protect': 'Cell欠压-保限值',
                'cell_uv_protect_resume': 'Cell欠压-保恢复值',
                'chg_oc_warn': '充-过流-警限值',
                'chg_oc_warn_resume': '充-过流-警恢复值',
                'chg_oc_protect': '充-过流-保护限值',
                'dis_oc_warn': '放-过流-警限值',
                'dis_oc_warn_resume': '放-过流-警恢复值',
                'dis_oc_protect': '放-过流-保护限值',
                'chg_ot_warn': '充-过温-警限值',
                'chg_ot_warn_resume': '充-过温-警恢复值',
                'chg_ot_protect': '充-过温-保护限值',
                'chg_ot_protect_resume': '充-过温-保护恢复值',
                'dis_ot_warn': '放-过温-警限值',
                'dis_ot_warn_resume': '放-过温-警恢复值',
                'dis_ot_protect': '放-过温-保护限值',
                'dis_ot_protect_resume': '放-过温-保护恢复值',
                'chg_ut_warn': '充-低温-警限值',
                'chg_ut_warn_resume': '充-低温-警恢复值',
                'chg_ut_protect': '充-低温-保护限值',
                'chg_ut_protect_resume': '充-低温-保护恢复值',
                'dis_ut_warn': '放-低温-警限值',
                'dis_ut_warn_resume': '放-低温-警恢复值',
                'dis_ut_protect': '放-低温-保护限值',
                'dis_ut_protect_resume': '放-低温-保护恢复值',
                'heater_start_temp': '加热器启动温度',
                'heater_stop_temp': '加热器关闭温度',
                
                # KB变量
                'pack_voltage_k': 'Pack电压K',
                'batt_voltage_k': 'Batt电压K',
                '500a_k': '50-500安K(注，不同电池，电流范围不同，谨慎参考)',
                '500a_b': '50-500安B',
                'n500a_k': '-(50-500)安K',
                'n500a_b': '-(50-500)安B',
                '50a_sk': '10-50安SK',
                '50a_sb': '10-50安SB',
                'n50a_sk': '-10-50安SK',
                'n50a_sb': '-10-50安SB',
                '10a_ssk': '0-10安SSK',
                '10a_ssb': '0-10安SSB',
                'n10a_ssk': '-(0-10)安SSK',
                'n10a_ssb': '-(0-10)安SSB',
                
                # 其他变量
                'ocp_delay_1c_chg': '1C充电过流保护延时',
                'ocp_delay_2c_chg': '2C充电过流保护延时',
                'ocp_delay_1c_dis': '1C放电过流保护延时',
                'ocp_delay_2c_dis': '2C放电过流保护延时',
                'rated_cap': '额定容量',
                'factory_cap': '出厂容量',
                'mos_temp_warn': 'MOS温度告警',
                'mos_temp_warn_resume': 'MOS温度告警恢复',
                'mos_temp_protect': 'MOS温度保护',
                'mos_temp_protect_resume': 'MOS温度保护恢复',
                'cycle_time': '循环时间累计',
                'single_chg_cap': '单次充电结合容量',
                
                # 版本信息
                'main_version': '主版本号',
                'minor_version': '次版本号',
                'revision_version': '修订版本号',
                'compile_year': '编译年份',
                'compile_month': '编译月份',
                'compile_date': '编译日期',
                'hardware_version': '硬件版本',
                'function_version': '功能版本',
                
                # INF变量
                'boot_main': 'boot主版本号',
                'boot_minor': 'boot次版本号',
                'boot_revision': 'boot修订版本号',
                'boot_year': 'boot年份',
                'boot_month': 'boot月份',
                'boot_date': 'boot日期',
                'boot_reserve1': 'boot保留1',
                'boot_reserve2': 'boot保留2',
                'app_main': 'app主版本号',
                'app_minor': 'app次版本号',
                'app_revision': 'app修订版本号',
                'app_year': 'app年份',
                'app_month': 'app月份',
                'app_date': 'app日期',
                'app_reserve1': 'app保留1',
                'app_reserve2': 'app保留2',
                'buff_main': 'buff主版本号',
                'buff_minor': 'buff次版本号',
                'buff_revision': 'buff修订版本号',
                'buff_year': 'buff年份',
                'buff_month': 'buff月份',
                'buff_date': 'buff日期',
                'buff_reserve1': 'buff保留1',
                'buff_reserve2': 'buff保留2',
                'back_main': 'back主版本号',
                'back_minor': 'back次版本号',
                'back_revision': 'back修订版本号',
                'back_year': 'back年份',
                'back_month': 'back月份',
                'back_date': 'back日期',
                'back_reserve1': 'back保留1',
                'back_reserve2': 'back保留2',
                'chip_name': '芯片名称',
                'writable_area': '可写区域',
                'pc_addr': 'PC地址',
                'unique_id': '唯一ID',
                
                # 序列号和保险丝
                'serial_number': '序列号',
                'fuse_enable': '保险丝使能',
                'fuse_status': '保险丝状态',
                
                # 集群信息
                'brand': '品牌',
                'current_rate': '当前倍率',
                'batt_module_cap': '电池模块容量',
                'cluster_cap': '集群容量',
                'total_batt_num': '总电池数量',
                'comm_fail_count': '通信失败次数',
                'bms_fail_count': 'BMS失败次数',
                'cell_fail_count': '电芯失败次数',
                'chg_mos_off_count': '充电MOS关次数',
                'dis_mos_off_count': '放电MOS关次数',
                'sys_max_cell_temp': '系统最高电芯温度',
                'sys_min_cell_temp': '系统最低电芯温度',
                'sys_max_cell_volt': '系统最高电芯电压',
                'sys_min_cell_volt': '系统最低电芯电压',
                'sys_max_batt_volt': '系统最高电池电压',
                'sys_min_batt_volt': '系统最低电池电压',
                'sys_max_current': '系统最大电流',
                'sys_min_current': '系统最小电流',
                'sys_max_soc': '系统最高SOC',
                'sys_min_soc': '系统最低SOC',
                'sys_max_soh': '系统最高SOH',
                'sys_min_soh': '系统最低SOH',
                'cluster_chg_volt_limit': '集群充电电压限制',
                'cluster_dis_volt_limit': '集群放电电压限制',
                'cluster_chg_cur_limit': '集群充电电流限制',
                'cluster_dis_cur_limit': '集群放电电流限制',
                'cluster_temp': '集群温度',
                'cluster_volt_v': '集群电压(V)',
                'cluster_curr_a': '集群电流(A)',
                'cluster_soc': '集群SOC',
                'cluster_soh': '集群SOH',
                'cluster_protect_stat': '集群保护状态',
                'cluster_fault_stat': '集群故障状态',
                'cluster_cycles': '集群循环次数',
            },
        },
        
        'en_US': {
            # ========== UI Text ==========
            'ui': {
                'window_title': 'Enhanced BMS Debug Tool - Multi-Window Manager',
                'user_app_title': 'Ampere Time Battery System Software',
                'control_panel': 'BMS Debug Tool Control Panel',
                'factory_mode': '🏭 Factory Mode',
                'simplified_window': '📱 Simplified Window',
                'cell_32_config': '⚡ 32-Cell Config',
                'cell_32_tooltip': 'Checked: 32 Cells + 15 Temp Sensors\nUnchecked: 16 Cells + SBS 5 Temps + KB 8 Temps',
                'open_connection': 'Open Connection',
                'disconnect': '🔌 Disconnect',
                'start_monitor': '▶️ Start Monitor',
                'stop_monitor': '⏸️ Stop Monitor',
                'query_version': '📋 Query Version',
                'clear_queue': '🗑️ Clear Queue',
                'select_all': 'Select All',
                'deselect_all': 'Deselect All',
                'read_all': '📖 Read All',
                'read': '🔄 Read',
                'write': '✏️ Write',
                'window_control_title': 'Data Window Control',
                'data_display_title': 'Data Display Windows',
                'status_disconnected': '⭕ Disconnected',
                'status_bluetooth': '🔗 Bluetooth Connected',
                'status_serial': '🔗 Serial Connected',
                'send_queue': '📤 Send Queue',
                'receive': '📥 Receive',
                'send': '📤 Send',
                'log_init': 'Enhanced Main Window Initialized',
                'log_factory_mode': 'Switched to Factory Mode',
                'log_user_mode': 'Switched to User Mode',
                'log_cell_config': 'Cell Configuration Changed',
                'log_16cell': '16 Cells + SBS 5 Temps + KB 8 Temps',
                'log_32cell': '32 Cells + 15 Temps',
                'log_loaded_config': 'Cell Configuration Loaded',
                'log_queue_cleared': 'Send Queue Cleared',
                'log_monitoring_start': 'Monitoring Started',
                'log_monitoring_start': 'Monitoring Started',
                'log_monitoring_stop': 'Monitoring Stopped',
                # newblue3_17.py window titles and UI elements
                'bt_tool_title': 'firstuse - Bluetooth Tool',
                'bt_tool_simplified_title': 'Bluetooth/Serial Connection',
                'startup_app': 'Starting application...',
                # Tab labels
                'tab_connection': 'Connection',
                'tab_control': 'Control',
                'tab_advanced': 'Advanced',
                'tab_test': 'Test',
                # Auto connect
                'auto_connect_group': 'Auto Connect',
                'auto_connect_enable': 'Enable',
                'device_name_label': 'Name:',
                'device_name_placeholder': 'Device Name',
                'mac_address_label': 'MAC:',
                'mac_address_placeholder': 'MAC Address (optional)',
                'interval_label': 'Interval:',
                'interval_seconds': 'sec',
                # Bluetooth connection
                'bt_connection_group': 'Bluetooth Connection',
                'device_list_label': 'Device List:',
                'rssi_threshold': 'RSSI >',
                'btn_connect': 'Connect',
                'btn_disconnect': 'Disconnect',
                'btn_connecting': 'Connecting...',
                'status_connected': '🔗 Connected',
                'status_connecting': '🔄 Connecting...',
                # Serial connection
                'serial_connection_group': 'Serial Connection',
                'serial_port_label': 'Port:',
                'baud_rate_label': 'Baud Rate:',
                'data_bits_label': 'Data Bits:',
                'stop_bits_label': 'Stop Bits:',
                'parity_label': 'Parity:',
                'parity_none': 'None',
                'parity_odd': 'Odd',
                'parity_even': 'Even',
                'btn_connect_serial': 'Connect Serial',
                'btn_disconnect_serial': 'Disconnect Serial',
                'monitor_interval_label': 'Monitor Interval:',
                # Scan button
                'btn_scan_refresh': '🔍 Scan & Refresh',
                # MOS control
                'mos_control_group': 'MOS Control',
                'btn_charge_on': 'Charge ON',
                'btn_charge_off': 'Charge OFF',
                'btn_discharge_on': 'Discharge ON',
                'btn_discharge_off': 'Discharge OFF',
                # Store power control
                'store_power_group': 'Store Power',
                'btn_store_power_on': 'Store ON',
                'btn_store_power_off': 'Store OFF',
                # Heating mode
                'heating_mode_group': 'Heating Mode',
                'btn_self_heating': 'Self Heating',
                'btn_charger_heating': 'Charger Heating',
                # RT control
                'rt_control_group': 'RT Control',
                'btn_rt0_on': 'RT0 ON',
                'btn_rt1_on': 'RT1 ON',
                'btn_rt2_on': 'RT2 ON',
                'btn_rt0_off': 'RT0 OFF',
                'btn_rt1_off': 'RT1 OFF',
                'btn_rt2_off': 'RT2 OFF',
                # Other control
                'other_control_group': 'Other Control',
                'btn_shutdown': '🔌 Shutdown Device',
                'bt_name_label': 'Name:',
                'bt_name_placeholder': 'Enter new BT name',
                'btn_change_bt_name': 'Change BT Name',
                # HEX file and programming
                'hex_file_group': 'HEX File',
                'btn_select_hex': 'Select HEX File',
                'hex_file_not_selected': 'No file selected',
                'hex_file_size': 'Size: {0} bytes',
                'hex_file_parse_failed': '❌ File parsing failed',
                'cell_32_config_checkbox': '32-Cell Config',
                # Password management
                'password_group': 'Password',
                'password_label': 'Password:',
                'password_placeholder': '6-digit password',
                'btn_query_lock': 'Query',
                'btn_login': 'Login',
                'btn_set_password': 'Set',
                'btn_reset_password': 'Reset',
                # Programming control
                'programming_group': 'Programming',
                'btn_start_programming': 'Start Program',
                'btn_stop_programming': 'Click to Stop',
                'packet_progress': 'Packet: {0} / {1}',
                'btn_batch_program': 'Batch Program',
                'btn_stop_batch': 'Click to Stop',
                'batch_success_count': 'Success: {0}',
                'batch_total_count': 'Total: {0} Success: {1}',
                # Test functions
                'send_test_group': 'Send Test',
                'send_input_label': 'Input:',
                'send_input_placeholder': 'Data to send',
                'checkbox_hex': 'HEX',
                'checkbox_crlf': '\\r\\n',
                'btn_send': 'Send',
                'btn_register': 'Register',
                'btn_connection_test': 'Connection Test',
                # Continuous send
                'continuous_send_group': 'Continuous Send',
                'interval1_label': 'Interval1:',
                'interval2_label': 'Interval2:',
                'btn_start_continuous': 'Start Continuous',
                'no_ack_count': 'No ACK={0}',
                'err_ack_count': 'ACK Error={0}',
                'total_send_count': 'Total={0}',
                # Receive data
                'receive_data_label': 'Received Data:',
                'checkbox_hex_display': 'HEX Display',
                'btn_clear_receive': 'Clear',
                # Heating mode control
                'heating_mode_title': 'Heating Mode',
                # Charge/discharge control
                'charge_discharge_control': 'Charge/Discharge',
                # Simplified window titles
                'simplified_bt_title': 'Bluetooth',
                'simplified_serial_title': 'Serial',
                'simplified_auto_connect': 'Auto Connect',
                'auto_save_hint': '💡 Auto Save',
                # Dynamic status text
                'scanning_devices': 'Scanning devices...',
                'bt_adapter_not_ready': 'Bluetooth adapter not ready, please check system settings',
                'devices_found': 'Bluetooth devices found:',
                'handshake_start': 'Starting handshake',
                'handshake_success': 'Handshake successful',
                'erase_success': 'Erase successful',
                'start_batch_100': 'Start Batch Program (100x)',
                # Version and company info
                'company_info': 'Shenzhen Ampere Time Digital New Energy Technology Co., Ltd. - Battery System Software v{0}',
                'version_info_title': 'Version Information:',
                'build_date': 'Build Date',
                'git_branch': 'Git Branch',
                'git_commit': 'Commit',
                'commit_message': 'Commit Message',
                'commit_author': 'Commit Author',
                'commit_time': 'Commit Time',
                'version_number': 'Version: v{0}',
                'version_read_error': 'Error reading version info: {0}',
                # Device connection status
                'unknown_device': 'Unknown Device',
                'unknown_port': 'Unknown Port',
                'bt_connected_with_addr': '🔗 BT Connected | 📱 {0} | 📍 {1}',
                'bt_connected_no_addr': '🔗 BT Connected | 📱 {0}',
                'serial_connected': '🔗 Serial Connected | 🔌 {0}',
                # Window configuration logs
                'log_windows_configured': '✅ {0} display windows configured',
                # Monitoring and command related
                'log_monitoring_error': 'Monitoring loop error: {0}',
                'log_send_command_failed': 'Send command failed: {0}',
                'log_mode_switched': 'Switched to {0} mode',
                'mode_factory': 'factory',
                'mode_user': 'user',
                'log_cell_config_switch': 'Cell configuration changed: {0}',
                'config_16cell_name': '16 Cells + SBS 5 Temps + KB 8 Temps',
                'config_32cell_name': '32 Cells + 15 Temps',
                'log_cell_config_loaded': 'Cell configuration loaded: {0}',
                'log_cell_config_sync_failed': 'Cell config sync failed: {0}',
                # Language switching
                'lang_name_zh': 'Simplified Chinese',
                'lang_name_en': 'English',
                'log_language_switched': 'Language switched to: {0}',
                'language_switched_title': 'Language Changed / 语言已切换',
                'language_switched_message': 'Language switched to: {0}\n界面语言已切换为: {0}\n\nNote: Some windows need to be reopened for full effect.\n注意：某些窗口需要重新打开才能完全生效。',
                'log_ui_update_error': 'UI text update error: {0}',
                # Data request logs
                'log_read_request': '🖱️ Manual read request: {0}',
                'log_read_command_not_found': 'Read command not found for window {0}',
                'log_write_request': 'Write request: {0}, modified items: {1}',
                'log_write_not_supported': 'Window {0} does not support write',
                'log_cannot_get_window_data': 'Cannot get window data',
                'log_value_convert_failed': 'Row {0} value conversion failed: {1}',
                'log_struct_format_not_found': 'Struct format not found: {0}',
                'log_pack_failed': 'Data packing failed: {0}',
                'log_command_construct_failed': 'Command construction failed: {0}',
                'log_write_command_sent': '✅ Write command sent: {0}',
                'log_write_request_failed': 'Write request failed: {0}',
                # Data processing errors
                'log_data_display_mgr_not_init': 'Error: data_display_mgr not initialized',
                'log_custom_process_error': 'custom_process_complete_data error: {0}',
                'log_update_window_data_failed': 'Update window data failed: {0}',
                'log_update_bit_flags_failed': 'Update bit flags window failed: {0}',
                'log_close_bt_window_error': 'Error closing BT window: {0}',
                # Program error
                'program_error': 'Program error: {0}',
                # Table headers
                'table_header_alarm': 'Alarm',
                'table_header_protect': 'Protect',
                'table_header_value': 'Value',
                'table_header_fault': 'Fault',
                'table_header_info': 'Info',
                'table_header_balance': 'Balance',
                'table_header_param_name': 'Param Name',
                'table_header_status_value': 'Status Value',
            },
            
            # ========== Status Bit Names ==========
            'status_bits': {
                'alarm': {
                    'pack_ov': 'PACK_OV',
                    'batt_ov': 'BATT_OV',
                    'cell_ov': 'CELL_OV',
                    'batt_uv': 'BATT_UV',
                    'cell_uv': 'CELL_UV',
                    'chg_oc': 'CHG_OC',
                    'dis_oc': 'DIS_OC',
                    'chg_ot': 'CHG_OT',
                    'dis_ot': 'DIS_OT',
                    'chg_ut': 'CHG_UT',
                    'dis_ut': 'DIS_UT',
                    'soc_l': 'SOC_L',
                    'end_life': 'END_LIFE',
                    'mos_ht': 'MOS_HT',
                },
                'protect': {
                    'pack_ov': 'PACK_OV',
                    'batt_ov': 'BATT_OV',
                    'cell_ov': 'CELL_OV',
                    'batt_uv': 'BATT_UV',
                    'cell_uv': 'CELL_UV',
                    'chg_oc': 'CHG_OC',
                    'dis_oc': 'DIS_OC',
                    'chg_ot': 'CHG_OT',
                    'dis_ot': 'DIS_OT',
                    'chg_ut': 'CHG_UT',
                    'dis_ut': 'DIS_UT',
                    'short': 'SHORT',
                    'rev': 'REV',
                    'chg_utoc': 'CHG_UTOC',
                    'chg_utov': 'CHG_UTOV',
                    'chg_short': 'CHG_SHORT',
                    'psp': 'PSP',
                    'bq_scd': 'BQ_SCD',
                    'bq_ocd': 'BQ_OCD',
                    'mos_ht': 'MOS_HT',
                    'chg_ut_limit': 'CHG_UT_LIM',
                },
                'fault': {
                    'v_sensor': 'V_SENSOR',
                    't_sensor': 'T_SENSOR',
                    'chg': 'CHG_FAIL',
                    'dis': 'DIS_FAIL',
                    'cell_bad': 'CELL_BAD',
                    'switch_off': 'SW_OFF',
                    'life_end': 'LIFE_END',
                    'bq_uv': 'BQ_UV',
                    'bq_ov': 'BQ_OV',
                    'bq_device': 'BQ_DEV',
                    'bq_overwr': 'BQ_OVRW',
                    'fuse_break': 'FUSE_BRK',
                },
                'info': {
                    'heater_config': 'HEAT_CFG',
                    'heater_on': 'HEAT_ON',
                    'chg_full_t': 'CHG_FULL_T',
                    'batt_full': 'BATT_FULL',
                    'chg_limited_on': 'CHG_LIM_ON',
                    'dis_limited_on': 'DIS_LIM_ON',
                    'chg_mos_off': 'CHG_MOS_OFF',
                    'dis_mos_off': 'DIS_MOS_OFF',
                    'lowvol_limit': 'LOW_V_LIM',
                    'lowtemp_forcechg': 'LOW_T_CHG',
                    'mult_batt': 'MULT_BATT',
                    'can_master': 'CAN_MASTER',
                    'can_slave': 'CAN_SLAVE',
                    'calendar_reach': 'CAL_REACH',
                    'test_kb': 'TEST_KB',
                    'calibrated_v': 'V_CAL',
                    'calibrated_c': 'C_CAL',
                    'lost_canbox': 'CAN_LOST',
                    'no_inv_timeout': 'NO_INV',
                    'fuseen_open': 'FUSE_OPEN',
                    'cell_cto': 'CELL_CTO',
                    'pswfunction_on': 'PSW_ON',
                    'powersave_on': 'PSAVE_ON',
                    'forceddis_on': 'FORCE_DIS',
                    'heatermode_self': 'SELF_HEAT',
                },
                'balance': {
                    'cell': 'C{0}',  # 格式化字符串，{0}会被替换为01-16
                },
                'battery_status': {
                    'idle': 'IDLE',
                    'charging': 'CHG',
                    'discharging': 'DIS',
                    'full': 'FULL',
                }
            },
            
            # ========== Window Titles ==========
            'windows': {
                'sbs': '📊 SBS Data',
                'bms': '⚙️ BMS Params',
                'kb': '📐 Calibration',
                'ocp_delay': '⏱️ OC Delay',
                'cell_cap': '🔋 Cell Cap',
                'mos_temp': '🌡️ MOS Temp',
                'life': '📅 Life Cycle',
                'version': '📋 Version',
                'info': 'ℹ️ System Info',
                'serial': '🔢 Serial Num',
                'fuse': '🔌 Fuse Info',
                'cluster': '🔗 Cluster Info',
                'alarm_protect': '⚠️ Alarm-Protect',
                'other_status': 'ℹ️ Other Status',
                'battery_status': '🔋 Battery Stat',
            },
            
            # ========== Variable Name Templates ==========
            'var_templates': {
                # SBS variables
                'pack_voltage': 'PACK Volt',
                'batt_voltage': 'BATT Volt',
                'cell_voltage': 'Cell {0} Volt',
                'cell_voltage_k': 'Cell {0} V-K',
                'current': 'Current',
                'temp': 'Temp {0}',
                'temp_k': 'Temp {0} K',
                'remain_cap': 'Remain Cap',
                'full_cap': 'Full Cap',
                'design_cap': 'Design Cap',
                'other_info': 'Other Info',
                'alarm_status': 'Alarm Stat',
                'protect_status': 'Protect Stat',
                'fault_status': 'Fault Stat',
                'balance_status': 'Balance Stat',
                'battery_status_label': 'Batt Status',
                'soc': 'SOC',
                'cap_health': 'Cap Health',
                'discharge_count': 'Dis Count',
                'total_discharge_cap': 'Total Dis Cap',
                'reserve': 'Reserve {0}',
                
                # BMS variables
                'chg_power_voltage': 'Chg Power Volt',
                'chg_power_diff': 'Chg Power Pack-Batt Diff',
                'chg_full_start': 'Chg Full Start Volt',
                'chg_full_stop': 'Chg Full Stop Volt',
                'pack_ov_warn': 'Pack OV Warn',
                'pack_ov_warn_resume': 'Pack OV Warn Resume',
                'pack_ov_protect': 'Pack OV Protect',
                'pack_ov_protect_resume': 'Pack OV Protect Resume',
                'batt_ov_warn': 'Batt OV Warn',
                'batt_ov_warn_resume': 'Batt OV Warn Resume',
                'batt_ov_protect': 'Batt OV Protect',
                'batt_ov_protect_resume': 'Batt OV Protect Resume',
                'cell_ov_warn': 'Cell OV Warn',
                'cell_ov_warn_resume': 'Cell OV Warn Resume',
                'cell_ov_protect': 'Cell OV Protect',
                'cell_ov_protect_resume': 'Cell OV Protect Resume',
                'batt_uv_warn': 'Batt UV Warn',
                'batt_uv_warn_resume': 'Batt UV Warn Resume',
                'batt_uv_protect': 'Batt UV Protect',
                'batt_uv_protect_resume': 'Batt UV Protect Resume',
                'cell_uv_warn': 'Cell UV Warn',
                'cell_uv_warn_resume': 'Cell UV Warn Resume',
                'cell_uv_protect': 'Cell UV Protect',
                'cell_uv_protect_resume': 'Cell UV Protect Resume',
                'chg_oc_warn': 'Chg OC Warn',
                'chg_oc_warn_resume': 'Chg OC Warn Resume',
                'chg_oc_protect': 'Chg OC Protect',
                'dis_oc_warn': 'Dis OC Warn',
                'dis_oc_warn_resume': 'Dis OC Warn Resume',
                'dis_oc_protect': 'Dis OC Protect',
                'chg_ot_warn': 'Chg OT Warn',
                'chg_ot_warn_resume': 'Chg OT Warn Resume',
                'chg_ot_protect': 'Chg OT Protect',
                'chg_ot_protect_resume': 'Chg OT Protect Resume',
                'dis_ot_warn': 'Dis OT Warn',
                'dis_ot_warn_resume': 'Dis OT Warn Resume',
                'dis_ot_protect': 'Dis OT Protect',
                'dis_ot_protect_resume': 'Dis OT Protect Resume',
                'chg_ut_warn': 'Chg UT Warn',
                'chg_ut_warn_resume': 'Chg UT Warn Resume',
                'chg_ut_protect': 'Chg UT Protect',
                'chg_ut_protect_resume': 'Chg UT Protect Resume',
                'dis_ut_warn': 'Dis UT Warn',
                'dis_ut_warn_resume': 'Dis UT Warn Resume',
                'dis_ut_protect': 'Dis UT Protect',
                'dis_ut_protect_resume': 'Dis UT Protect Resume',
                'heater_start_temp': 'Heater Start Temp',
                'heater_stop_temp': 'Heater Stop Temp',
                
                # KB variables
                'pack_voltage_k': 'Pack Volt K',
                'batt_voltage_k': 'Batt Volt K',
                '500a_k': '50-500A K (Note: diff batteries, diff ranges)',
                '500a_b': '50-500A B',
                'n500a_k': '-(50-500A) K',
                'n500a_b': '-(50-500A) B',
                '50a_sk': '10-50A SK',
                '50a_sb': '10-50A SB',
                'n50a_sk': '-10-50A SK',
                'n50a_sb': '-10-50A SB',
                '10a_ssk': '0-10A SSK',
                '10a_ssb': '0-10A SSB',
                'n10a_ssk': '-(0-10A) SSK',
                'n10a_ssb': '-(0-10A) SSB',
                
                # Other variables
                'ocp_delay_1c_chg': '1C Chg OC Protect Delay',
                'ocp_delay_2c_chg': '2C Chg OC Protect Delay',
                'ocp_delay_1c_dis': '1C Dis OC Protect Delay',
                'ocp_delay_2c_dis': '2C Dis OC Protect Delay',
                'rated_cap': 'Rated Cap',
                'factory_cap': 'Factory Cap',
                'mos_temp_warn': 'MOS Temp Warn',
                'mos_temp_warn_resume': 'MOS Temp Warn Resume',
                'mos_temp_protect': 'MOS Temp Protect',
                'mos_temp_protect_resume': 'MOS Temp Protect Resume',
                'cycle_time': 'Cycle Time Total',
                'single_chg_cap': 'Single Chg Cap',
                
                # Version info
                'main_version': 'Main Ver',
                'minor_version': 'Minor Ver',
                'revision_version': 'Revision Ver',
                'compile_year': 'Compile Year',
                'compile_month': 'Compile Month',
                'compile_date': 'Compile Date',
                'hardware_version': 'Hardware Ver',
                'function_version': 'Function Ver',
                
                # INF variables
                'boot_main': 'Boot Main Ver',
                'boot_minor': 'Boot Minor Ver',
                'boot_revision': 'Boot Revision Ver',
                'boot_year': 'Boot Year',
                'boot_month': 'Boot Month',
                'boot_date': 'Boot Date',
                'boot_reserve1': 'Boot Rsv1',
                'boot_reserve2': 'Boot Rsv2',
                'app_main': 'App Main Ver',
                'app_minor': 'App Minor Ver',
                'app_revision': 'App Revision Ver',
                'app_year': 'App Year',
                'app_month': 'App Month',
                'app_date': 'App Date',
                'app_reserve1': 'App Rsv1',
                'app_reserve2': 'App Rsv2',
                'buff_main': 'Buff Main Ver',
                'buff_minor': 'Buff Minor Ver',
                'buff_revision': 'Buff Revision Ver',
                'buff_year': 'Buff Year',
                'buff_month': 'Buff Month',
                'buff_date': 'Buff Date',
                'buff_reserve1': 'Buff Rsv1',
                'buff_reserve2': 'Buff Rsv2',
                'back_main': 'Back Main Ver',
                'back_minor': 'Back Minor Ver',
                'back_revision': 'Back Revision Ver',
                'back_year': 'Back Year',
                'back_month': 'Back Month',
                'back_date': 'Back Date',
                'back_reserve1': 'Back Rsv1',
                'back_reserve2': 'Back Rsv2',
                'chip_name': 'Chip Name',
                'writable_area': 'Writable Area',
                'pc_addr': 'PC Address',
                'unique_id': 'Unique ID',
                
                # Serial and Fuse
                'serial_number': 'Serial Number',
                'fuse_enable': 'Fuse Enable',
                'fuse_status': 'Fuse Status',
                
                # Cluster info
                'brand': 'Brand',
                'current_rate': 'Current Rate',
                'batt_module_cap': 'Batt Module Cap',
                'cluster_cap': 'Cluster Cap',
                'total_batt_num': 'Total Batt Num',
                'comm_fail_count': 'Comm Fail Count',
                'bms_fail_count': 'BMS Fail Count',
                'cell_fail_count': 'Cell Fail Count',
                'chg_mos_off_count': 'Chg MOS Off Count',
                'dis_mos_off_count': 'Dis MOS Off Count',
                'sys_max_cell_temp': 'Sys Max Cell Temp',
                'sys_min_cell_temp': 'Sys Min Cell Temp',
                'sys_max_cell_volt': 'Sys Max Cell Volt',
                'sys_min_cell_volt': 'Sys Min Cell Volt',
                'sys_max_batt_volt': 'Sys Max Batt Volt',
                'sys_min_batt_volt': 'Sys Min Batt Volt',
                'sys_max_current': 'Sys Max Current',
                'sys_min_current': 'Sys Min Current',
                'sys_max_soc': 'Sys Max SOC',
                'sys_min_soc': 'Sys Min SOC',
                'sys_max_soh': 'Sys Max SOH',
                'sys_min_soh': 'Sys Min SOH',
                'cluster_chg_volt_limit': 'Cluster Chg Volt Limit',
                'cluster_dis_volt_limit': 'Cluster Dis Volt Limit',
                'cluster_chg_cur_limit': 'Cluster Chg Cur Limit',
                'cluster_dis_cur_limit': 'Cluster Dis Cur Limit',
                'cluster_temp': 'Cluster Temp',
                'cluster_volt_v': 'Cluster Volt (V)',
                'cluster_curr_a': 'Cluster Curr (A)',
                'cluster_soc': 'Cluster SOC',
                'cluster_soh': 'Cluster SOH',
                'cluster_protect_stat': 'Cluster Protect Stat',
                'cluster_fault_stat': 'Cluster Fault Stat',
                'cluster_cycles': 'Cluster Cycles',
            },
        }
    }
    
    @classmethod
    def get_instance(cls):
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        # 从环境变量读取语言设置，默认英文
        # 注意：如果需要中文，请在程序启动前设置环境变量 APP_LANGUAGE='zh_CN'
        self.current_language = os.environ.get('APP_LANGUAGE', 'en_US')
    
    def t(self, key_path, *args):
        """
        翻译函数（简写为t）
        
        Args:
            key_path: 键路径，如 'ui.window_title' 或 'status_bits.alarm.pack_ov'
            *args: 格式化参数（用于替换 {0}, {1} 等占位符）
        
        Returns:
            str: 翻译后的文本
        """
        keys = key_path.split('.')
        data = self.TRANSLATIONS.get(self.current_language, self.TRANSLATIONS['en_US'])
        
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, key_path)
            else:
                return key_path
        
        # 支持格式化（替换 {0}, {1} 等）
        if args:
            try:
                return data.format(*args)
            except:
                return data
        return data
    
    def set_language(self, language):
        """
        切换语言
        
        Args:
            language: 语言代码，如 'zh_CN', 'en_US'
        
        Returns:
            bool: 切换成功返回 True，否则返回 False
        """
        if language in self.TRANSLATIONS:
            self.current_language = language
            os.environ['APP_LANGUAGE'] = language
            return True
        return False
    
    def get_current_language(self):
        """获取当前语言"""
        return self.current_language
    
    def get_available_languages(self):
        """获取所有可用语言"""
        return list(self.TRANSLATIONS.keys())


# 全局实例
_lang = LanguageManager.get_instance()


# 快捷函数
def t(key_path, *args):
    """
    翻译函数快捷方式
    
    用法示例：
        t('ui.window_title')  # 获取窗口标题
        t('status_bits.alarm.pack_ov')  # 获取告警状态名称
        t('var_templates.cell_voltage', 5)  # 获取"第【5】节电压"
    """
    return _lang.t(key_path, *args)


def set_language(language):
    """
    切换语言
    
    Args:
        language: 'zh_CN' 或 'en_US' 等
    """
    return _lang.set_language(language)


def get_current_language():
    """获取当前语言"""
    return _lang.get_current_language()

