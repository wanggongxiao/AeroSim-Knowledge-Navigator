import json

from app.process.import_.agent.main_graph import import_app
from app.process.import_.agent.state import create_default_state


def main() -> None:
    input_state = create_default_state(
        task_id="task_01",
        local_file_path="./***.md",
        is_pdf_read_enabled=True,
    )
    state = import_app.invoke(input_state)
    print(f"最终结果的 state:\n{json.dumps(state, indent=4, ensure_ascii=False)}")

    # 输出图结构，便于检查节点和边是否正确注册。
    import_app.get_graph().print_ascii()


if __name__ == "__main__":
    main()
