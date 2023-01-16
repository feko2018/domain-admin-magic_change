# -*- coding: utf-8 -*-
"""
@File    : notify_service.py
@Date    : 2022-10-30
@Author  : Peng Shiyu
"""
import requests
import pandas as pd


from domain_admin.enums.notify_type_enum import NotifyTypeEnum
from domain_admin.model.notify_model import NotifyModel
from domain_admin.utils.flask_ext.app_exception import AppException


def get_notify_row_value(user_id, type_id):
    """
    获取通知配置
    :param user_id:
    :param type_id:
    :return:
    """
    notify_row = NotifyModel.select().where(
        NotifyModel.user_id == user_id,
        NotifyModel.type_id == type_id
    ).get_or_none()

    if not notify_row:
        return None

    if not notify_row.value:
        return None

    return notify_row.value


def get_notify_email_list_of_user(user_id):
    """
    获取通知配置 - 邮箱列表
    :param user_id:
    :return:
    """
    notify_row_value = get_notify_row_value(user_id, NotifyTypeEnum.Email)

    if not notify_row_value:
        return None

    email_list = notify_row_value.get('email_list')

    if not email_list:
        return None

    return email_list


def get_notify_webhook_row_of_user(user_id):
    """
    获取通知配置 - webhook
    :param user_id:
    :return:
    """
    return get_notify_row_value(user_id, NotifyTypeEnum.WebHook)


def notify_webhook_of_user(user_id,domain_list=None):
    """
    通过 webhook 方式通知用户
    :param user_id:
    :return:
    """
    notify_webhook_row = get_notify_webhook_row_of_user(user_id)

    if not notify_webhook_row:
        raise AppException('webhook未设置')

    method = notify_webhook_row.get('method')
    url = notify_webhook_row.get('url')
    headers = notify_webhook_row.get('headers')
    body = notify_webhook_row.get('body')
    if len(body) == 0:
    ###修改企业微信告警格式###
        tmp_list=["<font color=\'warning\'>证书过期时间</font>   域名\n"]
        for i in domain_list[0]:#i[0] 域名，i[1]剩余天数，i[2]过期时间
            tmp_list.append("><font color=\'warning\'>%s</font> %s\n"%(i[2],i[0]))
        content= ''.join(tmp_list)
    #    df = pd.DataFrame(domain_list, columns=['域名', '剩余过期天数'])
    #    content=df.to_markdown()

        body = """{
       "msgtype": "markdown",
       "markdown": {
            "content": "证书有效期少于<font color=\'warning\'>%s</font>天有以下域名：\n
            %s\n
            具体信息请查看邮件！"
       },
       "enable_duplicate_check": 0,
       "duplicate_check_interval": 1800
    }"""%(domain_list[1],content)
    ###修改企业微信告警格式###

    if not url:
        raise AppException('url未设置')

    res = requests.request(method=method, url=url, headers=headers, data=body.encode('utf-8'))
    res.encoding = res.apparent_encoding

    return res.text
