import { defineStore } from 'pinia';
import axios from 'axios';

export const useMarketStore = defineStore('market', {
  state: () => ({
    candles: [],
    trades: [],
    portfolio: null,
    lastImportParams: null
  }),
  actions: {
    async importData(payload) {
      const response = await axios.post('/api/import', payload);
      this.lastImportParams = payload;
      return response.data;
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
      this.candles = response.data.items || [];
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
    }
  }
});
