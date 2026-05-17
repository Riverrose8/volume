# Исправления: Total Fees из GMGN

## ✅ Что было исправлено:

### 1. Убран fallback на calculate_total_fees()
**Было**: Использовался `calculate_total_fees()` если GMGN данные недоступны  
**Стало**: Используем **ТОЛЬКО** `total_fees_bnb` из GMGN

### 2. Исправлены отступы в фильтре
**Было**: `if EXCLUDE_LOW_TOTAL_FEES:` был внутри `if EXCLUDE_HIGH_BUNDLER:`  
**Стало**: Правильные отступы, фильтры независимы

### 3. Блокировка токенов без GMGN данных
**Было**: Если GMGN недоступен, токен проходил  
**Стало**: Если `total_fees_bnb` не получен из GMGN, токен блокируется

### 4. format_alert использует только GMGN данные
**Было**: Использовался `calculate_total_fees()` как fallback  
**Стало**: Показываем только `total_fees_bnb` из GMGN

## 📊 Результаты тестирования токенов:

### Токен 1: `0xdd2422a7f797cdfb060193bd20f514d8759c7777`
- ✅ **total_fees_bnb**: 0.000615 BNB (< 0.03) → **ДОЛЖЕН БЫТЬ ЗАБЛОКИРОВАН**
- ✅ top_10_holder_rate: 14.77%
- ✅ creator_open_count: 0
- ✅ buy_sell_ratio: 51.12

### Токен 2: `0x1a5acdd9467854a85b9c45fb20010ebb89114444`
- ✅ **total_fees_bnb**: 0.0299 BNB (< 0.03) → **ДОЛЖЕН БЫТЬ ЗАБЛОКИРОВАН**
- ✅ top_10_holder_rate: 0.03%
- ✅ creator_open_count: 0
- ✅ buy_sell_ratio: 1.02

### Токен 3: `0xae7b3bea74d81d3e4e75eb359a56bf3340ac7777`
- ✅ **total_fees_bnb**: 0.328 BNB (> 0.03) → **ДОЛЖЕН ПРОЙТИ**
- ✅ top_10_holder_rate: 14.46%
- ✅ creator_open_count: 0
- ✅ buy_sell_ratio: 1.63

## 🔍 Почему данные могут не показываться в уведомлениях:

1. **Данные получаются, но не передаются в format_alert**
   - Проверьте, что `token_data.update(gmgn_data)` выполняется ДО вызова `format_alert()`

2. **Данные получаются после вызова format_alert**
   - Проверьте порядок вызовов в коде

3. **Данные получаются, но поля имеют None**
   - Проверьте логи на наличие `✅ GMGN data fetched`

## 📝 Проверка на сервере:

```bash
# Проверьте логи на получение GMGN данных:
ssh ubuntu@158.160.78.224
cd ~/pancake-bot
tail -f new_tokens_bot.log | grep -E "GMGN data fetched|total_fees|Skipping.*total fees"
```

## ✅ Ожидаемое поведение:

1. Токены с `total_fees_bnb < 0.03 BNB` должны блокироваться
2. В уведомлениях должны показываться:
   - Total fees (только из GMGN)
   - Top 10% Holders (если получено)
   - Dev Previous Tokens (если получено)
   - Buy/Sell Ratio (если получено)
