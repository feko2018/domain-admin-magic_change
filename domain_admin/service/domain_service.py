# -*- coding: utf-8 -*-
import json
import traceback
from datetime import datetime

from playhouse.shortcuts import model_to_dict
from peewee import chunked
from domain_admin.log import logger
from domain_admin.model.base_model import db
from domain_admin.model.domain_model import DomainModel
from domain_admin.model.log_scheduler_model import LogSchedulerModel
from domain_admin.model.user_model import UserModel
from domain_admin.service import email_service, render_service
from domain_admin.service import file_service
from domain_admin.service import notify_service
from domain_admin.service import system_service
from domain_admin.utils import datetime_util, cert_util
from domain_admin.utils import domain_util
from domain_admin.utils.flask_ext.app_exception import AppException, ForbiddenAppException
from concurrent.futures import ThreadPoolExecutor


def add_domain(data):
    """
    添加域名
    :param data: {
        'domain': '必传',
        'user_id': '必传',
        'alias': '可选，默认 ""'
        'group_id': '可选，默认 0'
     }
    :return:
    """
    user_id = data['user_id']
    domain = data['domain']
    alias = data.get('alias', '')
    group_id = data.get('group_id', 0)
    notes = data.get('notes', '') # 新添加 备注
    row = DomainModel.create(
        user_id=user_id,
        domain=domain,
        alias=alias,
        group_id=group_id,
        notes=notes  # 新添加 备注
    )

    return row


def update_domain_cert_info(row):
    """
    更新域名的证书信息
    :param row:
    :return:
    """
    logger.info('update_domain_cert_info: %s', row.domain)

    connect_status = False
    expire_days = 0
    total_days = 0

    info = {}


    for i in range(1,3): # 尝试2次获取证书
        ntime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info("%s 第%s次获取证书 %s"%(ntime,i,row.domain))
        try:
            info = cert_util.get_cert_info(row.domain)
            if len(info)==0:
                connect_status = False  #返回空的话，说明证书对不上
            else:
                connect_status = True
                break
        except Exception:
            logger.error(traceback.format_exc())
    # try:
    #     info = cert_util.get_cert_info(row.domain)
    #     if len(info)==0:
    #         connect_status = False  #返回空的话，说明证书对不上
    #     else:
    #         connect_status = True
    # except Exception:
    #     logger.error(traceback.format_exc())

    start_date = info.get('start_date')
    expire_date = info.get('expire_date')

    if start_date and expire_date:
        now = datetime.now()
        start_time = datetime_util.parse_datetime(start_date)
        expire_time = datetime_util.parse_datetime(expire_date)

        expire_days = (expire_time - now).days
        total_days = (expire_time - start_time).days

    DomainModel.update(
        start_time=info.get('start_date'),
        expire_time=info.get('expire_date'),
        expire_days=expire_days,
        total_days=total_days,
        ip=info.get('ip', ''),
        connect_status=connect_status,
        detail_raw=json.dumps(info, ensure_ascii=False),
        check_time=datetime_util.get_datetime(),
    ).where(
        DomainModel.id == row.id
    ).execute()


def update_all_domain_cert_info():
    """
    更新所有域名信息
    :return:
    """
    lst = DomainModel.select()
    for row in lst:
        update_domain_cert_info(row)


def update_all_domain_cert_info_of_user(user_id):
    """
    更新用户的所有域名信息
    :return:
    """
    lst = DomainModel.select().where(
        DomainModel.user_id == user_id
    )

    for row in lst:
        update_domain_cert_info(row)


def get_domain_info_list(user_id=None):
    query = DomainModel.select()

    if user_id:
        query = query.where(
            DomainModel.user_id == user_id
        )

    query = query.order_by(
        DomainModel.expire_days.asc(),
        DomainModel.id.desc()
    )

    lst = list(map(lambda m: model_to_dict(
        model=m,
        exclude=[DomainModel.detail_raw],
        extra_attrs=[
            'start_date',
            'expire_date',
            # 'expire_days',
        ]
    ), query))

    # def compare(a, b):
    #     if a['expire_days'] and b['expire_days']:
    #         return a['expire_days'] - b['expire_days']
    #     else:
    #         if a['expire_days']:
    #             return a['expire_days']
    #         else:
    #             return -b['expire_days']

    # lst = sorted(lst, key=cmp_to_key(compare))

    return lst


def check_domain_cert(user_id):
    """
    查询域名证书到期情况
    :return:
    """
    user_row = UserModel.get_by_id(user_id)

    lst = get_domain_info_list(user_id)

    has_expired_domain = False

    for item in lst:
        if  item['expire_days'] <= user_row.before_expire_days: #个人设置
            has_expired_domain = True
            break

    if has_expired_domain:
        notify_user(user_id)
        # send_domain_list_email(user_id)


###修改企业微信告警格式###
def check_webhook_domain_cert(user_id):
    """
    查询域名证书到期情况,把过期的追加到list发送到webhook
    :return:
    """
    user_row = UserModel.get_by_id(user_id)
    expire_days= user_row.before_expire_days
    lst = get_domain_info_list(user_id)
    domain_list = []
    for item in lst:
        if  item['expire_days'] <= expire_days:
            domain_list.append([item["domain"],item["expire_days"],item["expire_date"],item["notes"]])##企业微信告警添加字段

    return domain_list,expire_days
###修改企业微信告警格式###



def update_and_check_all_domain_cert():
    log_row = LogSchedulerModel.create()

    error_message = ''

    status = True

    # 更新全部域名证书信息
    update_all_domain_cert_info()

    # 配置检查
    config = system_service.get_system_config()
    try:
        system_service.check_email_config(config)
    except Exception as e:
        logger.error(traceback.format_exc())

        status = False

        if isinstance(e, AppException):
            error_message = e.message
        else:
            error_message = str(e)

    # 全员发送
    if status:
        rows = UserModel.select()

        for row in rows:

            # 内层捕获单个用户发送错误
            try:
                check_domain_cert(row.id)
            except Exception as e:
                # traceback.print_exc()
                logger.error(traceback.format_exc())

                status = False

                if isinstance(e, AppException):
                    error_message = e.message
                else:
                    error_message = str(e)

    LogSchedulerModel.update({
        'status': status,
        'error_message': error_message,
        'update_time': datetime_util.get_datetime(),
    }).where(
        LogSchedulerModel.id == log_row
    ).execute()


def send_domain_list_email(user_id):
    """
    发送域名信息
    :param user_id:
    :return:
    """

    email_list = notify_service.get_notify_email_list_of_user(user_id)

    if not email_list:
        raise AppException('收件邮箱未设置')

    lst = get_domain_info_list(user_id)

    content = render_service.render_template('domain-cert-email.html', {'list': lst})

    email_service.send_email(
        content=content,
        to_addresses=email_list,
        content_type='html'
    )


def check_permission_and_get_row(domain_id, user_id):
    """
    权限检查
    :param domain_id:
    :param user_id:
    :return:
    """
    row = DomainModel.get_by_id(domain_id)
    if row.user_id != user_id:
        raise ForbiddenAppException()

    return row


def add_domain_from_file(filename, user_id):
    logger.info('add_domain_from_file')

    lst = domain_util.parse_domain_from_file(filename)
    # lst = [
    #     {
    #         'domain': domain,
    #         'user_id': user_id,
    #     } for domain in lst
    # ]
    sql_list=[]
    for i in lst: #新添加notes备注字段，需要
        if len(i.split()) >1:
            sql_list.append({
            'domain': i.split()[0],
            'notes': i.split()[1],
            'user_id': user_id,
        })
        else:
            sql_list.append({
                'domain': i.split()[0],
                'user_id': user_id,
            })
    print(sql_list)
    for batch in chunked(sql_list, 50):
        DomainModel.insert_many(batch).on_conflict_ignore().execute()

    # count = 0
    # for domain in lst:
    #     try:
    #         row = add_domain({
    #             'domain': domain,
    #             'user_id': user_id,
    #         })
    #
    #         # 导入后统一查询，避免太过耗时
    #         # update_domain_cert_info(row)
    #
    #         count += 1
    #     except Exception as e:
    #         # traceback.print_exc()
    #         logger.error(traceback.format_exc())

    # 查询
    update_all_domain_cert_info_of_user(user_id=user_id)

    # return count


def export_domain_to_file(user_id):
    rows = DomainModel.select().where(DomainModel.user_id == user_id)
    lst = [row.domain for row in rows]

    temp_filename = file_service.get_temp_filename('txt')

    with open(temp_filename, 'w') as f:
        f.writelines(lst)

    return temp_filename


def notify_user(user_id):
    """
    尝试通知用户
    :param user_id:
    :return:
    """
    try:
        send_domain_list_email(user_id)
    except:
        pass


    try:
        ###修改企业微信告警格式###
        domain_list = check_webhook_domain_cert(user_id)
        notify_service.notify_webhook_of_user(user_id,domain_list)
        ###修改企业微信告警格式###
    except Exception as e:
        logger.error(traceback.format_exc())
