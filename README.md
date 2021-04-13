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
from cbr_client import Client

client = Client(url='https://portal5test.cbr.ru/back/rapi2', 
                login='test', 
                password='test', 
                user_agent='test app')

files = [
        ('report.zip.enc', 'encrypted report content'),
        ('report.zip.enc.1.sig', 'operator signature'),
        ('report.zip.enc.2.sig', 'client signature')
    ]

# отправка отчета на портал ЦБ
# создание сообщения
msg = client.create_message(files, '1-ПИ')
# загрузка файлов
for f in msg.files:
    client.upload(f)
# или опциональная загрузка чанками
for f in msg.files:
    client.upload(f, chunked=True, chunk_size=2**16)
# финализация (закрытие сессии)
client.finalize_message(msg)

# получение квитанций
receipts = client.get_receipts(msg_id=msg.oid)
for rcpt in receipts:
    # получение файла из хранилища
    for f in rcpt.files:
        # сохраняется в f.content
        client.download(f)

# получение сообщений по типу формы
messages = client.get_messages(form='1-ПИ')
# или по статусу
messages = client.get_messages(status='draft')
# или по типу сообщения (inbox/outbox)
messages = client.get_messages(msg_type='outbox')
# паджинация, по умолчанию возвращается первая страница
messages = client.get_messages(status='draft', page=4)
# или комбинировать параметры как требуется 

# получение файлов сообщения
messages = client.get_messages()
for msg in messages:
    # получение файла из хранилища
    for f in msg.files:
        # сохраняется в f.content
        client.download(f)

# получение списка возможных задач
tasks = client.get_tasks()

# получение списка справочников с данными
dictionaries = client.get_dictionaries()

# получение данных из определенного справочника
d = client.get_dictionary(oid='dictionary_id')

# получение данных профиля
profile = client.get_profile()

# получение доступной квоты использования хранилища
quota = client.get_profile_quota()

# удаление сообщения 
client.delete_message(msg_id='message_id')
```
