<template>
  <div class="layout">
    <header class="layout__header">
      <h1>简易期货交易训练平台</h1>
      <p>离线历史回放 + 简易模拟交易</p>
    </header>
    <main class="layout__content">
      <section class="layout__left">
        <ImportForm class="panel" />
        <TradingPanel class="panel" />
      </section>
      <section class="layout__right">
        <CandleChart class="panel panel--chart" />
      </section>
    </main>
  </div>
</template>

<script setup>
import CandleChart from './components/CandleChart.vue';
import ImportForm from './components/ImportForm.vue';
import TradingPanel from './components/TradingPanel.vue';
</script>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.layout__header {
  padding: 16px 24px;
  background-color: #1e293b;
  color: #f8fafc;
}

.layout__content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.layout__left {
  width: 340px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.layout__right {
  flex: 1;
  padding: 16px 16px 16px 0;
  display: flex;
}

.panel {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.1);
}

.panel--chart {
  flex: 1;
  display: flex;
}
</style>
