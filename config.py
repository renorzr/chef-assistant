from dotenv import load_dotenv


def load_env_file(file_path: str = ".env") -> None:
    load_dotenv(dotenv_path=file_path, override=False)
