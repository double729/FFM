import { defineStore } from 'pinia';
import axios from 'axios';

export const useMarketStore = defineStore('market', {
  state: () => ({
    candles: [],
    contracts: [],
    trades: [],
    portfolio: null,
    lastImportParams: null,
    playbackStatus: null
  }),
  actions: {
    resetCandles() {
      this.candles = [];
    },
    appendCandles(items) {
      this.candles = [...this.candles, ...items];
    },
    async importData(payload) {
      const response = await axios.post('/api/import', payload);
      this.lastImportParams = payload;
      return response.data;
    },
    async loadContracts() {
      const response = await axios.get('/api/contracts');
      this.contracts = response.data.items || [];
    },
    async loadCandles(params) {
      const requestParams = params || this.lastImportParams;
      if (!requestParams) {
        return;
      }
      const response = await axios.get('/api/candles', {
        params: {
          symbol: requestParams.symbol,
          start_date: requestParams.start_date,
          end_date: requestParams.end_date,
          interval: requestParams.interval
        }
      });
      const items = response.data.items || [];
      this.candles = items;
    },
    async loadTrades() {
      const response = await axios.get('/api/trades');
      this.trades = response.data.items || [];
    },
    async createTrade(payload) {
      await axios.post('/api/trades', payload);
    },
    async deleteTrade(id) {
      await axios.delete(`/api/trades/${id}`);
    },
    async loadPortfolio() {
      const response = await axios.get('/api/portfolio');
      this.portfolio = response.data;
    },
    async startPlayback(params) {
      const payload = params || this.lastImportParams;
      if (!payload) {
        throw new Error('请先导入行情数据');
      }
      const response = await axios.post('/api/playback/start', payload);
      this.playbackStatus = response.data.status;
      this.lastImportParams = payload;
      this.candles = [];
      return this.playbackStatus;
    },
    async pausePlayback() {
      const response = await axios.post('/api/playback/pause');
      this.playbackStatus = response.data.status;
      return this.playbackStatus;
    },
    async resumePlayback() {
      const response = await axios.post('/api/playback/resume');
      this.playbackStatus = response.data.status;
      return this.playbackStatus;
    },
    async seekPlayback(timestamp) {
      const response = await axios.post('/api/playback/seek', { timestamp });
      this.playbackStatus = response.data.status;
      return this.playbackStatus;
    },
    async fetchPlaybackNext(count = 1) {
      const response = await axios.get('/api/playback/next', { params: { count } });
      const items = response.data.items || [];
      if (items.length) {
        this.appendCandles(items);
      }
      this.playbackStatus = response.data.status;
      return response.data;
    }
  }
});
