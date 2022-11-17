# cbr-client
![PyPI - License](https://img.shields.io/pypi/l/cbr-client)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cbr-client)

Клиент для работы с api ЦБ РФ

Описание АПИ - https://cbr.ru/lk_uio/guide/rest_api/

## Установка
```bash
pip install cbr-client
```

## Зависимости
* [httpx](https://github.com/encode/httpx)
* [pydantic](https://github.com/samuelcolvin/pydantic)


## Использование
```python
# необходимо запускать python -m asyncio
from cbr_client import Client

conn_params = dict(
    url='https://portal5test.cbr.ru',
    login='test',
    password='test',
    user_agent='test app'
)

client = Client(**conn_params)
# или через контекстный менеджер
# async with Client(**conn_params) as client:
#     ...

files = [
        ('report.zip.enc', b'encrypted report content'),
        ('report.zip.1.sig', b'operator signature'),
        ('report.zip.2.sig', b'client signature')
    ]

# отправка отчета на портал ЦБ
# создание сообщения
msg = await client.create_message(files, '1-ПИ')
# загрузка файлов
for f in msg.files:
    await client.upload(f)
# или опциональная загрузка чанками
for f in msg.files:
    await client.upload(f, chunked=True, chunk_size=2**16)
# финализация (закрытие сессии)
await client.finalize_message(msg)

# получение квитанций
receipts =await client.get_receipts(msg_id=msg.oid)
for rcpt in receipts:
    # получение файла из хранилища
    for f in rcpt.files:
        # сохраняется в f.content
        await client.download(f)

# получение сообщений по типу формы
messages = await client.get_messages(form='1-ПИ')
# или по статусу
messages = await client.get_messages(status='draft')
# или по типу сообщения (inbox/outbox)
messages = await client.get_messages(msg_type='outbox')
# паджинация, по умолчанию возвращается первая страница
messages = await client.get_messages(status='draft', page=4)
# или комбинировать параметры как требуется 

# получение файлов сообщения
messages = await client.get_messages()
for msg in messages:
    # получение файла из хранилища
    for f in msg.files:
        # сохраняется в f.content
        await client.download(f)

# получение списка возможных задач
tasks = await client.get_tasks()

# получение списка справочников с данными
dictionaries = await client.get_dictionaries()

# получение данных из определенного справочника
d = await client.get_dictionary(oid='dictionary_id')

# получение данных профиля
profile = await client.get_profile()

# получение доступной квоты использования хранилища
quota = await client.get_profile_quota()

# удаление сообщения 
await client.delete_message(msg_id='message_id')

# в конце работы не забываем закрывать соединение
await client.close()
```
