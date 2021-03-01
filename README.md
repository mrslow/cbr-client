# cbr-client
Клиент для работы с api ЦБ РФ

Описание АПИ - https://cbr.ru/lk_uio/guide/rest_api/

## Установка
```bash
pip install cbr-client
```

## Зависимости
* [httpx](https://github.com/encode/httpx)


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
msg = client.create_message(files, '1-ПИ')
client.upload(msg)
client.finalize_message(msg)

# получение квитанций
receipts = client.get_receipts(msg_id=msg.oid)
for rcpt in receipts:
    client.download(rcpt)
```
