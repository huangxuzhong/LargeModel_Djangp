import uuid
from app.utils.socket_client import TcpSocket


def remove_files(device_key, file_paths=[]):
    TcpSocket.send_data(
        {
            "type": "remove_files",
            "taskId": f"remove_{uuid.uuid4()}",
            "args": {"file_paths": file_paths},
        },
        device_key,
    )
