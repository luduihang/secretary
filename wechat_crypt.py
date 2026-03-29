import base64
import socket
import struct
import hashlib
import time
import os
from Crypto.Cipher import AES

class PKCS7Encoder:
    """提供基于 PKCS7 算法的加码与解码"""
    def __init__(self, block_size=32):
        self.block_size = block_size

    def encode(self, text_bytes):
        """对需要加密的明文进行填充"""
        text_length = len(text_bytes)
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        pad = bytes([amount_to_pad] * amount_to_pad)
        return text_bytes + pad

    def decode(self, decrypted):
        """删除解密后明文的填充内容"""
        pad = decrypted[-1]
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]

class WXBizMsgCrypt:
    def __init__(self, token: str, aes_key: str, corpid: str):
        self.token = token
        self.corpid = corpid
        # EncodingAESKey 在类初始化时需 Base64 解码
        try:
            self.key = base64.b64decode(aes_key + "=")
            assert len(self.key) == 32
        except Exception:
            raise Exception("Invalid EncodingAESKey")

    def get_signature(self, timestamp, nonce, encrypt_msg):
        """生成安全签名"""
        sort_list = sorted([self.token, timestamp, nonce, encrypt_msg])
        sha1 = hashlib.sha1()
        sha1.update("".join(sort_list).encode("utf-8"))
        return sha1.hexdigest()

    def decrypt(self, encrypted_msg: str):
        """
        解密企业微信消息
        :param encrypted_msg: 企业微信 POST 过来的加密 XML 中的 Encrypt 字段
        :return: (xml_content, receive_id)
        """
        try:
            # 1. Base64 解码并解密
            aes_cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            decrypted = aes_cipher.decrypt(base64.b64decode(encrypted_msg))
            
            # 2. 去除 PKCS7 填充
            unpadded = PKCS7Encoder().decode(decrypted)
            
            # 3. 提取 16 字节随机串、4 字节长度、XML 内容、CorpID
            # 这里的 content 结构: [16B Random] + [4B Len] + [XML] + [CorpID]
            xml_len = struct.unpack(">I", unpadded[16:20])[0]
            xml_content = unpadded[20 : 20 + xml_len].decode("utf-8")
            receive_id = unpadded[20 + xml_len :].decode("utf-8")
            
            return xml_content, receive_id
        except Exception as e:
            print(f"解密失败: {e}")
            return None, None

    def encrypt(self, reply_xml: str, nonce: str):
        """
        加密回复消息（如果需要被动回复加密 XML 时使用）
        """
        # 1. 拼接明文包
        random_str = os.urandom(16)
        xml_bytes = reply_xml.encode("utf-8")
        header = struct.pack(">I", len(xml_bytes))
        corpid_bytes = self.corpid.encode("utf-8")
        
        raw_bytes = random_str + header + xml_bytes + corpid_bytes
        
        # 2. 填充并加密
        padded_bytes = PKCS7Encoder().encode(raw_bytes)
        aes_cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        encrypted_bytes = aes_cipher.encrypt(padded_bytes)
        
        return base64.b64encode(encrypted_bytes).decode("utf-8")