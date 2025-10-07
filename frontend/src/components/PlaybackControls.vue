<template>
  <div class="playback">
    <header class="playback__header">
      <h2>行情回放</h2>
      <p v-if="status">进度：{{ progressText }}</p>
      <p v-else>尚未开始回放</p>
    </header>

    <form class="playback__form" @submit.prevent="start">
      <label class="playback__item">
        <span>品种</span>
        <input v-model="form.symbol" list="contractList" placeholder="如：rb2210" required />
        <datalist id="contractList">
          <option v-for="item in market.contracts" :key="`${item.symbol}-${item.interval}`" :value="item.symbol">
            {{ item.symbol }} ({{ item.interval }}: {{ formatDate(item.start_date) }} ~ {{ formatDate(item.end_date) }})
          </option>
        </datalist>
      </label>
      <label class="playback__item">
        <span>开始日期</span>
        <input v-model="form.start_date" type="date" required />
      </label>
      <label class="playback__item">
        <span>结束日期</span>
        <input v-model="form.end_date" type="date" required />
      </label>
      <label class="playback__item">
        <span>周期</span>
        <select v-model="form.interval">
          <option value="1d">日线</option>
          <option value="60">60分钟</option>
          <option value="30">30分钟</option>
          <option value="5">5分钟</option>
        </select>
      </label>
      <label class="playback__item">
        <span>回放速度</span>
        <select v-model.number="speed">
          <option :value="0.5">2x</option>
          <option :value="1">1x</option>
          <option :value="2">0.5x</option>
        </select>
      </label>
      <label class="playback__item">
        <span>每步条数</span>
        <input v-model.number="batchSize" type="number" min="1" max="20" />
      </label>

      <div class="playback__actions">
        <button type="submit" class="primary" :disabled="loading">
          {{ loading ? '启动中...' : '启动回放' }}
        </button>
        <button type="button" @click="toggle" :disabled="!status" class="secondary">
          {{ isPlaying ? '暂停' : '继续' }}
        </button>
        <button type="button" class="secondary" @click="step" :disabled="!status">单步</button>
        <button type="button" class="secondary" @click="reload" :disabled="loading">刷新合约</button>
      </div>
    </form>

    <p v-if="message" class="playback__message">{{ message }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import dayjs from 'dayjs';
import { useMarketStore } from '../stores/market';

const market = useMarketStore();

const form = reactive({
  symbol: '',
  start_date: '',
  end_date: '',
  interval: '1d'
});

const speed = ref(1);
const batchSize = ref(1);
const loading = ref(false);
const message = ref('');
const timer = ref(null);

const status = computed(() => market.playbackStatus);
const isPlaying = computed(() => status.value?.playing);

const progressText = computed(() => {
  if (!status.value) {
    return '0/0';
  }
  const current = status.value.current_index ?? 0;
  const total = status.value.total ?? 0;
  const currentTime = status.value.current_time ? dayjs(status.value.current_time).format('YYYY-MM-DD HH:mm') : '-';
  return `${current}/${total} @ ${currentTime}`;
});

const normalizedBatch = () => Math.max(1, Number(batchSize.value) || 1);

const scheduleTick = () => {
  clearInterval(timer.value);
  if (!isPlaying.value) {
    return;
  }
  const intervalMs = Math.max(100, speed.value * 1000);
  timer.value = setInterval(async () => {
    try {
      const result = await market.fetchPlaybackNext(normalizedBatch());
      if (!result.status?.playing || !result.has_more) {
        clearInterval(timer.value);
      }
    } catch (error) {
      clearInterval(timer.value);
      message.value = error?.response?.data?.message || error.message || '回放失败';
    }
  }, intervalMs);
};

watch(isPlaying, (value) => {
  if (value) {
    scheduleTick();
  } else {
    clearInterval(timer.value);
  }
});

watch(speed, () => {
  if (isPlaying.value) {
    scheduleTick();
  }
});

watch(
  () => market.lastImportParams,
  (params) => {
    if (params) {
      form.symbol = params.symbol || '';
      form.start_date = params.start_date || '';
      form.end_date = params.end_date || '';
      form.interval = params.interval || '1d';
    }
  },
  { immediate: true }
);

const formatDate = (value) => {
  if (!value) return '';
  return dayjs(value).format('YYYY-MM-DD');
};

const start = async () => {
  loading.value = true;
  message.value = '';
  try {
    const payload = {
      symbol: form.symbol,
      start_date: form.start_date,
      end_date: form.end_date,
      interval: form.interval
    };
    await market.startPlayback(payload);
    await market.fetchPlaybackNext(normalizedBatch());
  } catch (error) {
    message.value = error?.response?.data?.message || error.message || '启动回放失败';
  } finally {
    loading.value = false;
  }
};

const toggle = async () => {
  if (!status.value) return;
  try {
    if (isPlaying.value) {
      await market.pausePlayback();
    } else {
      await market.resumePlayback();
      await market.fetchPlaybackNext(normalizedBatch());
    }
  } catch (error) {
    message.value = error?.response?.data?.message || error.message || '切换状态失败';
  }
};

const step = async () => {
  if (!status.value) return;
  try {
    await market.fetchPlaybackNext(normalizedBatch());
  } catch (error) {
    message.value = error?.response?.data?.message || error.message || '单步失败';
  }
};

const reload = async () => {
  try {
    await market.loadContracts();
  } catch (error) {
    message.value = error?.response?.data?.message || error.message || '刷新失败';
  }
};

onMounted(async () => {
  await reload();
});

onUnmounted(() => {
  clearInterval(timer.value);
});
</script>

<style scoped>
.playback {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.playback__header h2 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.playback__header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #475569;
}

.playback__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.playback__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.playback__item span {
  font-size: 13px;
  color: #64748b;
}

.playback__item input,
.playback__item select {
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #cbd5f5;
}

.playback__actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
}

.primary,
.secondary {
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: 600;
}

.primary {
  background: linear-gradient(120deg, #2563eb, #4f46e5);
  color: #ffffff;
}

.secondary {
  background: #e2e8f0;
  color: #1e293b;
}

.secondary:disabled,
.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.playback__message {
  font-size: 12px;
  color: #dc2626;
}
</style>
