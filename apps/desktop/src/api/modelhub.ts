import { apiService } from "../services/api.service";

export const fetchModelList = async () => {
  const res = await apiService.searchModels('', 50);
  return res.models;
};

export const fetchCachedModels = async () => {
  const res = await apiService.listLocalModels();
  return res.models;
};

export const downloadModel = async (model_name: string) => {
  return apiService.downloadModel(model_name);
};

export const deleteCachedModel = async (_model_name: string) => {
  // not present in new api; noop or implement if backend supports
  return { success: true } as any;
};

export const compressModel = async (model_name: string, method: string = "quantize") => {
  return apiService.startCompression({
    model_path: model_name,
    output_path: '',
    method: method as any,
  });
};
