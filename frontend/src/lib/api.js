import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const t = localStorage.getItem("gl_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export const imgUrl = (assetId) => {
  const t = localStorage.getItem("gl_token");
  return `${API}/images/${assetId}/download?auth=${encodeURIComponent(t || "")}`;
};
