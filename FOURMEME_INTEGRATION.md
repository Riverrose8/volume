# Four.Meme Integration Guide

## 🚀 **Интеграция Four.Meme завершена!**

### **✅ Что добавлено:**

1. **Bitquery API интеграция** - получение данных с Four.Meme
2. **Парсер Four.Meme токенов** - обработка данных в unified формат
3. **Интеграция в основной цикл** - Four.Meme как источник данных
4. **Логирование** - отслеживание Four.Meme токенов

### **🔧 Настройка:**

#### **1. Получить Bitquery API ключ:**
1. Зарегистрироваться на [bitquery.io](https://bitquery.io)
2. Создать API ключ в разделе "Access API"
3. Добавить ключ в `.env` файл:

```bash
BITQUERY_API_KEY=your_bitquery_api_key_here
```

#### **2. Обновить бота на сервере:**
```bash
# Скопировать обновленный код
scp main.py ubuntu@84.201.161.90:~/pancake-bot/

# Перезапустить бота
ssh -l ubuntu 84.201.161.90 "sudo systemctl restart pancake-bot.service"
```

### **📊 Как это работает:**

#### **До интеграции:**
- ❌ Токены торгуются только на Four.Meme
- ❌ GeckoTerminal не видит Four.Meme
- ❌ Бот пропускает токены до миграции

#### **После интеграции:**
- ✅ Бот получает данные с Four.Meme через Bitquery
- ✅ Ловит токены ДО миграции на PancakeSwap
- ✅ Отслеживает прогресс bonding curve
- ✅ Предупреждает о готовящихся миграциях

### **🎯 Примеры использования:**

#### **Отслеживание новых токенов:**
```graphql
query {
  EVM(dataset: combined, network: bsc) {
    DEXTradeByTokens(
      where: {
        Trade: {
          Dex: {ProtocolName: {is: "fourmeme_v1"}}
        }
      }
    ) {
      Trade {
        Currency {
          Name
          Symbol
          SmartContract
        }
      }
      volumeUsd: sum(of: Trade_Side_AmountInUSD)
    }
  }
}
```

#### **Отслеживание миграций:**
```graphql
subscription {
  EVM(network: bsc) {
    Events(
      where: {
        Log: { Signature: { Name: { in: ["PairCreated"] } } }
        Transaction: {
          To: { is: "0x5c952063c7fc8610ffdb798152d69f0b9550762b" }
        }
      }
    ) {
      Arguments {
        Name
        Value {
          ... on EVM_ABI_Address_Value_Arg {
            address
          }
        }
      }
    }
  }
}
```

### **🔍 Мониторинг:**

После настройки в логах бота появятся записи:
```
✅ Bitquery: fetched 15 Four.Meme tokens
🔍 Four.Meme token: PEPE - Vol: $450,000, Age: 0.5h, New: True, NotPopular: True
```

### **📈 Преимущества:**

1. **Раннее обнаружение** - токены ловятся до миграции
2. **Больше возможностей** - доступ к Four.Meme экосистеме
3. **Прогнозирование** - отслеживание bonding curve прогресса
4. **Конкурентное преимущество** - другие боты не видят Four.Meme

### **⚠️ Важные моменты:**

1. **API лимиты** - Bitquery имеет лимиты запросов
2. **Стоимость** - Bitquery платный сервис
3. **Надежность** - зависимость от внешнего API
4. **Задержки** - данные могут приходить с задержкой

### **🎉 Результат:**

Теперь токен "同舟计划" и подобные будут ловиться **ДО** миграции на PancakeSwap, что даст значительное конкурентное преимущество!
