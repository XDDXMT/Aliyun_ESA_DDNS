# -*- coding: utf-8 -*-
import json
import sys
import yaml
import ast
import requests
import time
import schedule
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from alibabacloud_esa20240910.client import Client as ESA20240910Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_esa20240910 import models as esa20240910_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_credentials.client import Client as CredClient
from alibabacloud_credentials.models import Config as CredConfig
import functools
import threading
import logging
import os


# 颜色定义
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # 背景色
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

    # 样式
    UNDERLINE = '\033[4m'


# 配置日志
class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    LEVEL_COLORS = {
        'DEBUG': Colors.CYAN,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.BG_RED + Colors.WHITE
    }

    def format(self, record):
        # 保存原始级别
        levelname = record.levelname
        # 添加颜色
        if levelname in self.LEVEL_COLORS:
            record.levelname = f"{self.LEVEL_COLORS[levelname]}{levelname}{Colors.RESET}"
            record.msg = f"{self.LEVEL_COLORS[levelname]}{record.msg}{Colors.RESET}"

        # 调用父类格式化
        result = super().format(record)
        # 恢复原始级别
        record.levelname = levelname
        return result


# 创建彩色打印函数
def cprint(text, color=Colors.RESET, bold=False, end='\n'):
    """彩色打印"""
    style = Colors.BOLD if bold else ''
    print(f"{style}{color}{text}{Colors.RESET}", end=end, flush=True)


# 配置日志处理器
def setup_logging():
    """配置彩色日志"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 移除所有现有的处理器
    logger.handlers.clear()

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # 创建文件处理器
    file_handler = logging.FileHandler('ddns_updater.log')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# 初始化日志
logger = setup_logging()

# 全局变量
running = True
manual_scan_requested = False
scan_lock = threading.Lock()


# 信号处理器
def signal_handler(signum, frame):
    global running
    cprint(f"\n接收到信号 {signum}，正在优雅退出...", Colors.YELLOW, bold=True)
    logger.info(f"接收到信号 {signum}，正在优雅退出...")
    running = False


# 命令行输入处理器
def command_input_handler():
    """命令行输入处理器线程"""
    global running, manual_scan_requested

    cprint("\n" + "=" * 60, Colors.CYAN)
    cprint("DDNS更新服务已启动！", Colors.GREEN, bold=True)
    cprint("=" * 60, Colors.CYAN)
    cprint("\n可用命令：", Colors.MAGENTA, bold=True)
    cprint("  start  - 立即执行一次新的扫描", Colors.WHITE)
    cprint("  status - 显示当前状态", Colors.WHITE)
    cprint("  help   - 显示帮助信息", Colors.WHITE)
    cprint("  exit   - 退出程序", Colors.WHITE)
    cprint("  clear  - 清空屏幕", Colors.WHITE)
    cprint("-" * 40, Colors.CYAN)


    while running:
        try:
            # 彩色提示符
            prompt = f"{Colors.GREEN}DDNS>{Colors.RESET} "
            command = input(prompt).strip().lower()

            if command == 'start':
                cprint("正在启动新的扫描...", Colors.BLUE, bold=True)
                logger.info("用户请求手动扫描")
                with scan_lock:
                    manual_scan_requested = True

            elif command == 'status':
                show_status()

            elif command == 'help':
                show_help()

            elif command == 'exit' or command == 'quit':
                cprint("正在退出程序...", Colors.YELLOW, bold=True)
                running = False

            elif command == 'clear':
                os.system('cls' if os.name == 'nt' else 'clear')
                cprint("屏幕已清空", Colors.CYAN)

            elif command:
                cprint(f"未知命令: {command}", Colors.RED)
                cprint("输入 'help' 查看可用命令", Colors.YELLOW)

        except (KeyboardInterrupt, EOFError):
            cprint("\n接收到中断信号，正在退出...", Colors.YELLOW, bold=True)
            running = False
            break
        except Exception as e:
            cprint(f"命令处理错误: {e}", Colors.RED)
            logger.error(f"命令处理错误: {e}")


def show_status():
    """显示当前状态"""
    global running
    cprint("\n" + "=" * 40, Colors.MAGENTA)
    cprint("DDNS服务状态", Colors.CYAN, bold=True)
    cprint("=" * 40, Colors.MAGENTA)
    cprint(f"运行状态: {'运行中' if running else '停止中'}", Colors.GREEN)
    cprint(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.WHITE)
    cprint(f"进程ID: {os.getpid()}", Colors.WHITE)

    # 计算下一个整点执行时间
    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    wait_seconds = (next_hour - now).total_seconds()
    cprint(f"下次执行: {next_hour.strftime('%Y-%m-%d %H:%M:%S')}", Colors.YELLOW)
    cprint(f"剩余时间: {int(wait_seconds // 3600)}小时{int((wait_seconds % 3600) // 60)}分钟{int(wait_seconds % 60)}秒",
           Colors.YELLOW)
    cprint("=" * 40, Colors.MAGENTA)


def show_help():
    """显示帮助信息"""
    cprint("\n" + "=" * 50, Colors.CYAN)
    cprint("DDNS更新服务 - 帮助", Colors.GREEN, bold=True)
    cprint("=" * 50, Colors.CYAN)
    cprint("命令说明：", Colors.MAGENTA, bold=True)
    cprint(f"  {Colors.GREEN}start{Colors.RESET}  - 立即执行一次DDNS扫描和更新", Colors.WHITE)
    cprint(f"  {Colors.GREEN}status{Colors.RESET} - 显示服务状态和下次执行时间", Colors.WHITE)
    cprint(f"  {Colors.GREEN}help{Colors.RESET}  - 显示此帮助信息", Colors.WHITE)
    cprint(f"  {Colors.GREEN}exit{Colors.RESET}  - 退出程序 (或使用 Ctrl+C)", Colors.WHITE)
    cprint(f"  {Colors.GREEN}clear{Colors.RESET} - 清空屏幕", Colors.WHITE)
    cprint("\n定时执行：", Colors.MAGENTA, bold=True)
    cprint("  程序会在每小时整点自动执行DDNS更新", Colors.WHITE)
    cprint("  启动时会立即执行第一次更新", Colors.WHITE)
    cprint("  使用 'start' 命令可随时手动触发更新", Colors.WHITE)
    cprint("\n日志文件：", Colors.MAGENTA, bold=True)
    cprint("  详细日志保存在 ddns_updater.log 文件中", Colors.WHITE)
    cprint("=" * 50, Colors.CYAN)


# 修改主函数
def main():
    global running, manual_scan_requested

    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动命令行输入线程
    input_thread = threading.Thread(target=command_input_handler, daemon=True)
    input_thread.start()

    # 第一次启动时立即执行一次
    logger.info("第一次启动，立即执行DDNS更新...")
    cprint("\n正在执行首次DDNS更新...", Colors.BLUE, bold=True)
    run_ddns_update()

    # 计算到下一个整点的等待时间
    wait_seconds = wait_until_next_hour()

    # 主循环
    while running:
        try:
            # 检查是否需要手动扫描
            with scan_lock:
                if manual_scan_requested:
                    cprint("\n" + "=" * 60, Colors.YELLOW)
                    cprint("执行手动扫描...", Colors.BLUE, bold=True)
                    logger.info("开始执行手动扫描")
                    run_ddns_update()
                    cprint("手动扫描完成!", Colors.GREEN, bold=True)
                    cprint("=" * 60, Colors.YELLOW)
                    manual_scan_requested = False

            # 分段等待，以便能够响应退出信号和命令
            for _ in range(int(wait_seconds)):
                if not running:
                    break
                time.sleep(1)

                # 每秒检查一次手动扫描请求
                with scan_lock:
                    if manual_scan_requested:
                        break

            if not running:
                break

            # 执行定时DDNS更新
            logger.info(f"整点执行DDNS更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            cprint(f"\n[{datetime.now().strftime('%H:%M:%S')}] 执行定时DDNS更新...",
                   Colors.CYAN, bold=True)
            run_ddns_update()

            # 计算下一个整点的等待时间
            wait_seconds = wait_until_next_hour()

        except KeyboardInterrupt:
            cprint("\n接收到中断信号，正在退出...", Colors.YELLOW, bold=True)
            break
        except Exception as e:
            logger.error(f"主循环中发生错误: {e}")
            cprint(f"错误: {e}", Colors.RED)
            # 出错后等待5分钟再重试
            time.sleep(300)

    cprint("\nDDNS更新服务已停止", Colors.YELLOW, bold=True)
    logger.info("DDNS更新服务已停止")


# 修改check_and_update_ip函数，添加颜色输出
def check_and_update_ip(record_id: int, new_ip: Optional[str] = None,
                        auto_update: bool = True) -> Dict[str, Any]:
    """
    检查并更新IP地址，如果IP不同则更新最新的IP
    """
    result = {
        "record_id": record_id,
        "local_ip": "",
        "record_ip": "",
        "ip_changed": False,
        "update_performed": False,
        "update_result": None
    }

    cprint("\n" + "=" * 60, Colors.BLUE)
    cprint(f"开始检查并更新IP地址 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
           Colors.GREEN, bold=True)
    logger.info("=" * 60)
    logger.info(f"开始检查并更新IP地址 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 获取当前IP
    if new_ip:
        local_ip = new_ip
        cprint(f"使用指定的IP: {local_ip}", Colors.CYAN)
        logger.info(f"使用指定的IP: {local_ip}")
    else:
        cprint("1. 正在获取本机公网IP...", Colors.WHITE)
        logger.info("1. 正在获取本机公网IP...")
        local_ip = get_local_ip()
        if not local_ip:
            cprint("错误: 无法获取本机IP地址", Colors.RED, bold=True)
            logger.error("错误: 无法获取本机IP地址")
            return {**result, "error": "无法获取本机IP地址"}
        cprint(f"   本机公网IP: {Colors.GREEN}{local_ip}{Colors.RESET}", Colors.WHITE, bold=True)
        logger.info(f"   本机公网IP: {local_ip}")

    result["local_ip"] = local_ip

    # 2. 获取阿里云ESA中的记录值
    cprint("2. 正在查询阿里云ESA记录...", Colors.WHITE)
    logger.info("2. 正在查询阿里云ESA记录...")

    try:
        record_info = get_domain_record(record_id)

        if "error" in record_info:
            cprint(f"错误: 获取记录信息失败 - {record_info['error']}", Colors.RED, bold=True)
            logger.error(f"错误: 获取记录信息失败 - {record_info['error']}")
            return {**result, "error": f"获取记录信息失败: {record_info['error']}"}

        # 从记录信息中提取IP地址
        record_data = record_info.get("Data", {})
        if isinstance(record_data, dict):
            record_ip = record_data.get("Value", "")
        else:
            record_ip = str(record_info.get("Data", ""))

        record_name = record_info.get("RecordName", "未知")
        record_priority = record_data.get("priority", 10) if isinstance(record_data, dict) else 10

        cprint(f"   记录名称: {Colors.CYAN}{record_name}{Colors.RESET}", Colors.WHITE)
        cprint(f"   记录ID: {Colors.CYAN}{record_id}{Colors.RESET}", Colors.WHITE)
        cprint(f"   记录值(IP): {Colors.CYAN}{record_ip if record_ip else '空'}{Colors.RESET}", Colors.WHITE)

        logger.info(f"   记录名称: {record_name}")
        logger.info(f"   记录ID: {record_id}")
        logger.info(f"   记录值(IP): {record_ip if record_ip else '空'}")

        result["record_ip"] = record_ip
        result["record_name"] = record_name
        result["record_priority"] = record_priority

        # 3. 比较IP地址
        cprint("3. 比较IP地址...", Colors.WHITE)
        logger.info("3. 比较IP地址...")

        if not record_ip:
            cprint("   警告: 记录中的IP地址为空", Colors.YELLOW)
            logger.warning("警告: 记录中的IP地址为空")
            ip_changed = True
        elif local_ip == record_ip:
            cprint(f"   结果: {Colors.GREEN}IP地址相同{Colors.RESET}", Colors.WHITE)
            cprint(f"   本机IP: {Colors.GREEN}{local_ip}{Colors.RESET}", Colors.WHITE)
            cprint(f"   记录IP: {Colors.GREEN}{record_ip}{Colors.RESET}", Colors.WHITE)
            logger.info(f"   结果: IP地址相同")
            logger.info(f"   本机IP: {local_ip}")
            logger.info(f"   记录IP: {record_ip}")
            ip_changed = False
        else:
            cprint(f"   结果: {Colors.YELLOW}IP地址不同!{Colors.RESET}", Colors.WHITE, bold=True)
            cprint(f"   本机IP: {Colors.GREEN}{local_ip}{Colors.RESET}", Colors.WHITE)
            cprint(f"   记录IP: {Colors.RED}{record_ip}{Colors.RESET}", Colors.WHITE)
            logger.info(f"   结果: IP地址不同!")
            logger.info(f"   本机IP: {local_ip}")
            logger.info(f"   记录IP: {record_ip}")
            ip_changed = True

        result["ip_changed"] = ip_changed

        # 4. 如果IP不同且允许自动更新，则更新记录
        if ip_changed and auto_update:
            cprint("4. 正在更新记录到最新IP...", Colors.WHITE)
            logger.info("4. 正在更新记录到最新IP...")

            # 获取原记录的其他设置
            proxied = record_info.get("Proxied", False)
            ttl = record_info.get("Ttl", 1)
            record_type = record_info.get("Type", "A/AAAA")

            update_result = update_domain_record(
                record_id=record_id,
                new_ip=local_ip,
                priority=record_priority,
                proxied=proxied,
                ttl=ttl,
                record_type=record_type
            )

            result["update_performed"] = True
            result["update_result"] = update_result

            if update_result.get("success"):
                cprint(f"   记录已成功更新到: {Colors.GREEN}{local_ip}{Colors.RESET}",
                       Colors.WHITE, bold=True)
                logger.info(f"   记录已成功更新到: {local_ip}")
            else:
                cprint(f"   记录更新失败: {update_result.get('error', '未知错误')}",
                       Colors.RED, bold=True)
                logger.error(f"   记录更新失败: {update_result.get('error', '未知错误')}")
        elif ip_changed and not auto_update:
            cprint("4. IP地址不同，但auto_update=False，跳过更新", Colors.YELLOW)
            logger.info("4. IP地址不同，但auto_update=False，跳过更新")
        else:
            cprint("4. IP地址相同，无需更新", Colors.GREEN)
            logger.info("4. IP地址相同，无需更新")

    except Exception as e:
        cprint(f"错误: 比较IP地址时发生错误 - {e}", Colors.RED, bold=True)
        logger.error(f"错误: 比较IP地址时发生错误 - {e}")
        import traceback
        traceback.print_exc()
        return {**result, "error": str(e)}

    logger.info("=" * 60)
    logger.info("检查完成")
    cprint("\n" + "=" * 60, Colors.BLUE)
    cprint("检查完成", Colors.GREEN, bold=True)

    return result


# 修改run_ddns_update函数，添加颜色输出
def run_ddns_update():
    """执行DDNS更新任务"""
    try:
        config = load_config()
        # 从配置中获取record_id
        record_id = config.get("record_id", 3942378189367488)

        # 如果需要从aliyun部分获取
        if "aliyun" in config and "record_id" in config["aliyun"]:
            record_id = config["aliyun"]["record_id"]

        # 执行DDNS更新
        result = check_and_update_ip(record_id)

        # 记录结果
        cprint("\n" + "=" * 60, Colors.MAGENTA)
        cprint("结果摘要:", Colors.CYAN, bold=True)
        cprint("=" * 60, Colors.MAGENTA)

        status_color = Colors.GREEN if not result.get('error') else Colors.RED
        cprint(f"记录ID: {result.get('record_id')}", Colors.WHITE)
        cprint(f"本机IP: {result.get('local_ip')}", Colors.WHITE)
        cprint(f"记录IP: {result.get('record_ip')}", Colors.WHITE)

        if result.get('ip_changed'):
            ip_status = f"{Colors.YELLOW}是{Colors.RESET}"
        else:
            ip_status = f"{Colors.GREEN}否{Colors.RESET}"
        cprint(f"IP是否变化: {ip_status}", Colors.WHITE)

        if result.get('update_performed'):
            update_status = f"{Colors.YELLOW}是{Colors.RESET}"
        else:
            update_status = f"{Colors.CYAN}否{Colors.RESET}"
        cprint(f"是否执行更新: {update_status}", Colors.WHITE)

        if result.get('update_result'):
            if result['update_result'].get('success'):
                update_result = f"{Colors.GREEN}成功{Colors.RESET}"
            else:
                update_result = f"{Colors.RED}失败{Colors.RESET}"
            cprint(f"更新结果: {update_result}", Colors.WHITE)

        if result.get('error'):
            cprint(f"错误信息: {result['error']}", Colors.RED)
        cprint("=" * 60, Colors.MAGENTA)

        # 同时记录到日志
        logger.info("=" * 60)
        logger.info("结果摘要:")
        logger.info(f"记录ID: {result.get('record_id')}")
        logger.info(f"本机IP: {result.get('local_ip')}")
        logger.info(f"记录IP: {result.get('record_ip')}")
        logger.info(f"IP是否变化: {'是' if result.get('ip_changed') else '否'}")
        logger.info(f"是否执行更新: {'是' if result.get('update_performed') else '否'}")

        if result.get('update_result'):
            logger.info(f"更新结果: {'成功' if result['update_result'].get('success') else '失败'}")

        if result.get('error'):
            logger.error(f"错误信息: {result['error']}")
        logger.info("=" * 60)

    except Exception as e:
        cprint(f"执行DDNS更新时发生错误: {e}", Colors.RED, bold=True)
        logger.error(f"执行DDNS更新时发生错误: {e}")


# 保留原有函数（未修改部分保持不变）
def load_config(config_path: str = "config.yml") -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        raise


def create_client() -> ESA20240910Client:
    """创建阿里云ESA客户端"""
    cfg = load_config()

    cred_cfg = CredConfig(
        type="access_key",
        access_key_id=cfg["aliyun"]["access_key_id"],
        access_key_secret=cfg["aliyun"]["access_key_secret"]
    )
    cred_client = CredClient(cred_cfg)

    config = open_api_models.Config(
        credential=cred_client,
        region_id=cfg["aliyun"]["region"],
        endpoint="esa.cn-hangzhou.aliyuncs.com"
    )

    return ESA20240910Client(config)


def get_local_ip() -> str:
    """
    获取本机公网IP
    """
    try:
        # 使用ipplus360获取本机IP
        response = requests.get("https://www.ipplus360.com/getIP", timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get("success") and data.get("code") == 200:
            return data.get("data", "")
        else:
            logger.error(f"获取IP失败: {data.get('msg', '未知错误')}")
            return ""

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {e}")
        return ""
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"获取本机IP时发生未知错误: {e}")
        return ""


def parse_response_string(response_str: str) -> Dict[str, Any]:
    """
    解析响应字符串为字典
    """
    try:
        # 如果响应是字符串格式的字典，先转换为真正的字典
        if isinstance(response_str, str):
            # 使用ast安全地解析字符串格式的字典
            response_dict = ast.literal_eval(response_str)
        else:
            # 如果已经是字典，直接使用
            response_dict = response_str

        return response_dict
    except (ValueError, SyntaxError, TypeError) as e:
        logger.error(f"解析响应字符串失败: {e}")
        # 尝试使用json解析
        try:
            # 将单引号替换为双引号以适应JSON格式
            json_str = response_str.replace("'", '"').replace("False", "false").replace("True", "true")
            return json.loads(json_str)
        except Exception as json_e:
            logger.error(f"JSON解析也失败: {json_e}")
            return {}


def get_record_info(record_id: int) -> Dict[str, Any]:
    """
    获取域名记录详细信息
    """
    client = create_client()
    get_record_request = esa20240910_models.GetRecordRequest(record_id=record_id)
    runtime = util_models.RuntimeOptions()

    try:
        resp = client.get_record_with_options(get_record_request, runtime)

        # 将响应转换为字典格式
        # 先检查是否有to_map()方法
        if hasattr(resp, 'to_map'):
            resp_dict = resp.to_map()
        elif hasattr(resp, '__dict__'):
            resp_dict = resp.__dict__
        else:
            # 尝试转换为字符串然后解析
            resp_str = str(resp)
            resp_dict = parse_response_string(resp_str)

        return resp_dict
    except Exception as error:
        # 可以记录日志或抛出更具体的异常
        error_msg = getattr(error, 'message', str(error))
        logger.error(f"获取记录信息失败: {error_msg}")

        if hasattr(error, 'data') and error.data:
            logger.error(f"诊断地址: {error.data.get('Recommend', '无')}")
        raise error


def extract_record_data(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    从响应中提取关键信息
    """
    if not response:
        return {}

    result = {}

    # 添加headers和statusCode
    if "headers" in response:
        result["headers"] = response.get("headers", {})
    if "statusCode" in response:
        result["statusCode"] = response.get("statusCode", 0)

    # 添加body中的信息
    body = response.get("body", {})

    if not body:
        return result

    # 如果body中有RecordModel，则提取
    if "RecordModel" in body:
        record_model = body.get("RecordModel", {})

        # 复制所有RecordModel的字段到结果
        for key, value in record_model.items():
            if key not in ["__class__", "__dict__", "__weakref__"]:  # 排除Python内部属性
                result[key] = value

    # 添加RequestId
    if "RequestId" in body:
        result["RequestId"] = body.get("RequestId")

    return result


def get_domain_record(record_id: int, extract_only: bool = True) -> Dict[str, Any]:
    """
    获取域名记录的便捷函数
    """
    try:
        response = get_record_info(record_id)
        if extract_only:
            return extract_record_data(response)
        return response
    except Exception as e:
        return {"error": str(e), "status": "failed"}


def update_domain_record(record_id: int, new_ip: str, priority: int = 10,
                         proxied: bool = False, ttl: int = 1, record_type: str = 'A/AAAA') -> Dict[str, Any]:
    """
    更新域名记录到指定的IP地址
    """
    logger.info(f"准备更新记录 {record_id} 到新IP: {new_ip}")

    client = create_client()

    # 构建data对象
    data = esa20240910_models.UpdateRecordRequestData(
        value=new_ip,
        priority=priority
    )

    # 构建更新请求
    update_record_request = esa20240910_models.UpdateRecordRequest(
        data=data,
        proxied=proxied,
        ttl=ttl,
        record_id=record_id,
        type=record_type
    )

    runtime = util_models.RuntimeOptions()

    try:
        logger.info("正在调用阿里云API更新记录...")
        resp = client.update_record_with_options(update_record_request, runtime)

        # 将响应转换为字典格式
        if hasattr(resp, 'to_map'):
            resp_dict = resp.to_map()
        elif hasattr(resp, '__dict__'):
            resp_dict = resp.__dict__
        else:
            resp_str = str(resp)
            resp_dict = parse_response_string(resp_str)

        logger.info(f"记录 {record_id} 更新成功!")
        return {
            "success": True,
            "record_id": record_id,
            "new_ip": new_ip,
            "response": resp_dict
        }

    except Exception as error:
        error_msg = getattr(error, 'message', str(error))
        logger.error(f"更新记录失败: {error_msg}")

        if hasattr(error, 'data') and error.data:
            logger.error(f"诊断地址: {error.data.get('Recommend', '无')}")

        return {
            "success": False,
            "record_id": record_id,
            "error": error_msg,
            "status": "failed"
        }


def wait_until_next_hour():
    """等待到下一个整点"""
    now = datetime.now()
    # 计算下一个整点的时间
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    # 计算需要等待的秒数
    wait_seconds = (next_hour - now).total_seconds()

    logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"下次执行时间: {next_hour.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"等待 {wait_seconds:.1f} 秒 ({wait_seconds / 3600:.2f} 小时)")

    # 添加彩色输出
    cprint(f"\n下次定时执行: {next_hour.strftime('%Y-%m-%d %H:%M:%S')}",
           Colors.MAGENTA, bold=True)
    cprint(f"等待时间: {wait_seconds / 3600:.2f} 小时", Colors.CYAN)

    return wait_seconds


if __name__ == '__main__':
    main()