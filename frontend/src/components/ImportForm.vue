<template>
  <div>
    <h2>行情导入</h2>
    <form class="form" @submit.prevent="onSubmit">
      <label class="form__item">
        <span>品种代码</span>
        <input v-model="symbol" placeholder="如：rb2210" required />
      </label>
      <label class="form__item">
        <span>开始日期</span>
        <input v-model="startDate" type="date" required />
      </label>
      <label class="form__item">
        <span>结束日期</span>
        <input v-model="endDate" type="date" required />
      </label>
      <label class="form__item">
        <span>周期</span>
        <select v-model="interval">
          <option value="1d">日线</option>
          <option value="60">60分钟</option>
          <option value="30">30分钟</option>
          <option value="5">5分钟</option>
        </select>
      </label>
      <button class="form__submit" type="submit" :disabled="loading">
        {{ loading ? '正在导入...' : '导入数据' }}
      </button>
    </form>
    <p v-if="message" class="form__message">{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useMarketStore } from '../stores/market';

const market = useMarketStore();
const symbol = ref('');
const startDate = ref('');
const endDate = ref('');
const interval = ref('1d');
const loading = ref(false);
const message = ref('');

const onSubmit = async () => {
  if (!symbol.value || !startDate.value || !endDate.value) {
    message.value = '请完整填写导入信息';
    return;
  }
  loading.value = true;
  message.value = '';
  try {
    const result = await market.importData({
      symbol: symbol.value,
      start_date: startDate.value,
      end_date: endDate.value,
      interval: interval.value
    });
    message.value = `成功导入 ${result.imported} 条记录`;
    await market.loadCandles();
  } catch (error) {
    message.value = error?.response?.data?.message || error.message || '导入失败';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form__item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form__item span {
  font-size: 14px;
  color: #475569;
}

.form__item input,
.form__item select {
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #cbd5f5;
}

.form__submit {
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(120deg, #2563eb, #4f46e5);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
}

.form__submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form__message {
  margin-top: 8px;
  font-size: 13px;
  color: #0f172a;
}
</style>
