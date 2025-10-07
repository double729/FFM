<template>
  <div>
    <h2>模拟交易</h2>
    <form class="form" @submit.prevent="onSubmit">
      <label class="form__item">
        <span>品种</span>
        <input v-model="trade.symbol" placeholder="与导入的品种保持一致" required />
      </label>
      <label class="form__item">
        <span>方向</span>
        <select v-model="trade.direction">
          <option value="buy">做多</option>
          <option value="sell">做空</option>
        </select>
      </label>
      <label class="form__item">
        <span>价格</span>
        <input v-model.number="trade.price" type="number" step="0.01" required />
      </label>
      <label class="form__item">
        <span>手数</span>
        <input v-model.number="trade.quantity" type="number" min="1" required />
      </label>
      <label class="form__item">
        <span>备注</span>
        <input v-model="trade.note" placeholder="可选" />
      </label>
      <button class="form__submit" type="submit" :disabled="loading">
        {{ loading ? '提交中...' : '提交交易' }}
      </button>
    </form>

    <section class="trades">
      <header class="trades__header">
        <h3>交易记录</h3>
        <button class="trades__refresh" type="button" @click="refresh">刷新</button>
      </header>
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>品种</th>
            <th>方向</th>
            <th>价格</th>
            <th>数量</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in market.trades" :key="item.id">
            <td>{{ formatTime(item.trade_time) }}</td>
            <td>{{ item.symbol }}</td>
            <td>{{ item.direction === 'buy' ? '多' : '空' }}</td>
            <td>{{ Number(item.price).toFixed(2) }}</td>
            <td>{{ item.quantity }}</td>
            <td>
              <button type="button" class="link" @click="removeTrade(item.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="portfolio" v-if="market.portfolio">
      <h3>持仓与盈亏</h3>
      <div v-for="(position, symbol) in market.portfolio.positions" :key="symbol" class="portfolio__row">
        <div>
          <strong>{{ symbol }}</strong>
          <p>手数：{{ position.quantity }}</p>
        </div>
        <div>
          <p>均价：{{ Number(position.average_price || 0).toFixed(2) }}</p>
          <p>最新价：{{ Number(position.last_price || 0).toFixed(2) }}</p>
        </div>
      </div>
      <footer class="portfolio__footer">
        <span>未实现盈亏：{{ Number(market.portfolio.unrealized_pnl).toFixed(2) }}</span>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import dayjs from 'dayjs';
import { useMarketStore } from '../stores/market';

const market = useMarketStore();
const loading = ref(false);

const trade = reactive({
  symbol: '',
  direction: 'buy',
  price: 0,
  quantity: 1,
  note: ''
});

const onSubmit = async () => {
  loading.value = true;
  try {
    await market.createTrade(trade);
    await refresh();
    trade.price = 0;
    trade.quantity = 1;
    trade.note = '';
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const refresh = async () => {
  await Promise.all([market.loadTrades(), market.loadPortfolio()]);
};

const removeTrade = async (id) => {
  await market.deleteTrade(id);
  await refresh();
};

const formatTime = (value) => dayjs(value).format('YYYY-MM-DD HH:mm');

refresh();
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
  background: linear-gradient(120deg, #f97316, #ea580c);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
}

.trades {
  margin-top: 20px;
}

.trades table {
  width: 100%;
  border-collapse: collapse;
}

.trades th,
.trades td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 12px;
}

.trades__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.trades__refresh,
.link {
  border: none;
  background: none;
  color: #2563eb;
  cursor: pointer;
}

.portfolio {
  margin-top: 20px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
}

.portfolio__row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.portfolio__footer {
  font-weight: 600;
}
</style>
