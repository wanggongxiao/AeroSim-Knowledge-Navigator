import os

from app.process.import_.agent.nodes.node_md_img import node_md_img
from app.shared.runtime.logger import logger
from app.shared.utils.path_util import PROJECT_ROOT


def main() -> None:
    logger.info(f"本地测试 - 项目根目录：{PROJECT_ROOT}")

    test_md_path = os.path.join(
        PROJECT_ROOT,
        "output",
        "hak180使用说明书",
        "hak180使用说明书.md",
    )

    if not os.path.exists(test_md_path):
        logger.error(f"本地测试 - 测试文件不存在：{test_md_path}")
        return

    test_state = {
        "md_path": test_md_path,
        "task_id": "test_task_123456",
        "md_content": "",
    }

    logger.info("开始本地测试 - MD 图片处理全流程")
    result_state = node_md_img(test_state)
    logger.info(f"本地测试完成 - 处理结果状态：{result_state}")


if __name__ == "__main__":
    main()