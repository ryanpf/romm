<script setup lang="ts">
// VideosSubtab: the Media tab's Videos panel. The user's own gallery videos
// (private until shared from their edit dialog) and other users' public ones.
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { UserVideoSchema } from "@/__generated__";
import ScreenshotEditDialog from "@/components/GameDetails/ScreenshotEditDialog.vue";
import VideosTab, {
  type VideoItem,
} from "@/components/GameDetails/VideosTab.vue";
import { useConfirm } from "@/composables/useConfirm";
import { useRomSync } from "@/composables/useRomSync";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RDropzone } from "@/lib";
import videoApi from "@/services/api/video";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import { errorMessage } from "@/utils/errorMessage";

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { refetchRom } = useRomSync();
const uploadStore = storeUpload();
const { user } = storeToRefs(storeAuth());

function toItem(video: UserVideoSchema, isOwn: boolean): VideoItem {
  return {
    id: video.id,
    url: video.download_path,
    posterUrl: video.screenshot?.download_path,
    isOwn,
    isPublic: Boolean(video.is_public),
    ...(isOwn
      ? {}
      : {
          username: video.username,
          userId: video.user_id,
          userAvatarPath: video.user_avatar_path,
          userUpdatedAt: video.user_updated_at,
        }),
  };
}

const allVideos = computed(() => props.rom.all_user_videos ?? []);
const isMine = (video: UserVideoSchema) =>
  user.value?.id != null && video.user_id === user.value.id;
const myVideos = computed(() =>
  allVideos.value.filter(isMine).map((v) => toItem(v, true)),
);
const communityVideos = computed(() =>
  allVideos.value.filter((v) => !isMine(v)).map((v) => toItem(v, false)),
);

async function refreshRom() {
  await refetchRom(props.rom.id);
}

// ---------- Upload ----------
const myDz = ref<InstanceType<typeof RDropzone> | null>(null);

async function handleMyFiles(files: File[]) {
  if (files.length === 0) return;
  const responses = await videoApi.uploadGalleryVideos({
    romId: props.rom.id,
    filesToUpload: files,
  });
  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;
  if (failed === 0) uploadStore.reset();
  if (successful > 0) {
    snackbar.success(
      failed
        ? t("rom.videos-uploaded-with-failed", successful, {
            named: { n: successful, failed },
          })
        : t("rom.videos-uploaded-n", successful, { named: { n: successful } }),
      { icon: "mdi-check-bold", timeout: 3000 },
    );
    await refreshRom();
  } else {
    snackbar.warning(t("rom.no-videos-uploaded"), {
      icon: "mdi-close-circle",
      timeout: 5000,
    });
  }
}

// ---------- Delete ----------
async function deleteMyVideo(id: number) {
  const ok = await confirm({
    title: t("rom.delete-video-title"),
    body: t("rom.delete-video-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await videoApi.deleteVideo({ id });
    await refreshRom();
    snackbar.success(t("rom.video-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.video-remove-failed", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
  }
}

// ---------- Edit ----------
const editTarget = ref<VideoItem | null>(null);
const savingEdit = ref(false);

async function submitEdit(isPublic: boolean) {
  const target = editTarget.value;
  if (!target || savingEdit.value) return;
  savingEdit.value = true;
  try {
    await videoApi.setVideoVisibility({ id: target.id, isPublic });
    await refreshRom();
    if (editTarget.value === target) editTarget.value = null;
    snackbar.success(t("rom.video-updated"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("common.cant-update-visibility", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    savingEdit.value = false;
  }
}
</script>

<template>
  <div class="r-videos">
    <section class="r-videos__section">
      <header class="r-videos__head">
        <h3 class="r-videos__title">{{ t("rom.videos-section-mine") }}</h3>
        <RBtn
          v-if="myVideos.length > 0"
          variant="outlined"
          size="small"
          prepend-icon="mdi-cloud-upload-outline"
          @click="myDz?.open()"
        >
          {{ t("common.upload") }}
        </RBtn>
      </header>

      <RDropzone
        v-if="myVideos.length === 0"
        :title="t('rom.videos-empty')"
        :hint="t('common.dropzone-hint')"
        :active-title="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-videos')"
        accept="video/*"
        multiple
        @files="handleMyFiles"
      />
      <RDropzone
        v-else
        ref="myDz"
        overlay
        :release-label="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-videos')"
        accept="video/*"
        multiple
        @files="handleMyFiles"
      >
        <VideosTab
          :videos="myVideos"
          editable
          @edit="editTarget = $event"
          @delete="deleteMyVideo"
        />
      </RDropzone>
    </section>

    <section v-if="communityVideos.length > 0" class="r-videos__section">
      <header class="r-videos__head">
        <h3 class="r-videos__title">
          {{ t("rom.videos-section-community") }}
        </h3>
      </header>
      <VideosTab :videos="communityVideos" />
    </section>

    <ScreenshotEditDialog
      :model-value="editTarget !== null"
      :is-public="!!editTarget?.isPublic"
      :busy="savingEdit"
      :title="t('rom.edit-video')"
      @update:model-value="!$event && (editTarget = null)"
      @submit="submitEdit"
    />
  </div>
</template>

<style scoped>
.r-videos {
  display: flex;
  flex-direction: column;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}

.r-videos__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-videos__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.r-videos__title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
</style>
