import axios from "axios";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: apiBase,
  timeout: 12000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API error", error);
    return Promise.reject(error);
  }
);
