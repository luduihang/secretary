import os
print(os.path.exists("/home/ubuntu/secretary/scripts"))  # 应返回 True
print(os.listdir("/home/ubuntu/secretary/scripts"))     # 应包含 mongo_client.py