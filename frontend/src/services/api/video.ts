import type { AxiosProgressEvent } from "axios";
import type { VideoSchema } from "@/__generated__";
import api from "@/services/api";
import storeUpload from "@/stores/upload";
import { toError } from "@/utils/toError";

// Mirrors the gallery screenshot upload flow (upload-store progress + allSettled).
async function uploadGalleryVideos({
  romId,
  filesToUpload,
}: {
  romId: number;
  filesToUpload: File[];
}) {
  const uploadStore = storeUpload();

  const promises = filesToUpload.map((file) => {
    const formData = new FormData();
    formData.append("videoFile", file);

    uploadStore.start(file.name);
    return new Promise<VideoSchema>((resolve, reject) => {
      api
        .post<VideoSchema>("/videos", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          params: { rom_id: romId },
          onUploadProgress: (progressEvent: AxiosProgressEvent) => {
            uploadStore.update(file.name, progressEvent);
          },
        })
        .then(({ data }) => resolve(data))
        .catch((error) => {
          uploadStore.fail(file.name, error.response?.data?.detail);
          reject(toError(error));
        });
    });
  });

  return Promise.allSettled(promises);
}

async function deleteVideo({ id }: { id: number }) {
  return api.delete(`/videos/${id}`);
}

async function setVideoVisibility({
  id,
  isPublic,
}: {
  id: number;
  isPublic: boolean;
}) {
  return api.put<VideoSchema>(`/videos/${id}`, { is_public: isPublic });
}

export default {
  uploadGalleryVideos,
  deleteVideo,
  setVideoVisibility,
};
