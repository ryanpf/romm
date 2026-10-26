<script setup lang="ts">
// VideosTab: responsive grid of 16:9 gallery videos, each played in place.
// Owned videos can be edited (visibility) and deleted; community ones show
// their owner.
import { useI18n } from "vue-i18n";
import PublicBadge from "@/components/shared/PublicBadge.vue";
import { RAvatar, RBtn } from "@/lib";
import { userAvatarUrl } from "@/utils/userAvatar";

export type VideoItem = {
  id: number;
  url: string;
  posterUrl?: string | undefined;
  isOwn: boolean;
  isPublic: boolean;
  username?: string | undefined;
  userId?: number | null | undefined;
  userAvatarPath?: string | null | undefined;
  userUpdatedAt?: string | null | undefined;
};

defineOptions({ inheritAttrs: false });

defineProps<{
  videos: VideoItem[];
  editable?: boolean;
}>();
const emit = defineEmits<{
  edit: [video: VideoItem];
  delete: [id: number];
}>();

const { t } = useI18n();
</script>

<template>
  <section v-bind="$attrs" class="r-det-videos">
    <div
      v-for="(video, i) in videos"
      :key="video.id"
      class="r-det-videos__cell r-asset-fade"
      :style="{ '--asset-fade-i': i }"
    >
      <!-- Gameplay clips ship no caption track. -->
      <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
      <video
        class="r-det-videos__media"
        :src="video.url"
        :poster="video.posterUrl"
        :aria-label="t('rom.video-num', { n: i + 1 })"
        controls
        preload="metadata"
      />

      <div v-if="video.username" class="r-det-videos__owner">
        <RAvatar
          :image="
            userAvatarUrl({
              userId: video.userId,
              avatarPath: video.userAvatarPath,
              updatedAt: video.userUpdatedAt,
            })
          "
          size="16"
        />
        <span>{{ video.username }}</span>
      </div>

      <PublicBadge
        v-else-if="editable && video.isOwn && video.isPublic"
        class="r-det-videos__badge"
      />

      <div v-if="editable && video.isOwn" class="r-det-videos__actions">
        <RBtn
          icon="mdi-pencil-outline"
          size="small"
          variant="flat"
          color="primary"
          :aria-label="t('rom.edit-video')"
          :tooltip="t('rom.edit-video')"
          @click="emit('edit', video)"
        />
        <RBtn
          icon="mdi-delete"
          size="small"
          variant="flat"
          color="romm-red"
          :aria-label="t('rom.video-num-delete', { n: i + 1 })"
          :tooltip="t('common.delete')"
          @click="emit('delete', video.id)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-det-videos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
  padding: 6px 6px 4px;
}

.r-det-videos__cell {
  position: relative;
}

.r-det-videos__media {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  background: var(--r-color-cover-placeholder);
  object-fit: contain;
}

/* Top corners: the player's own controls take the bottom edge. */
.r-det-videos__actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-det-videos__cell:hover .r-det-videos__actions,
.r-det-videos__cell:focus-within .r-det-videos__actions {
  opacity: 1;
}
/* No hover to reveal them with at phone and tablet widths. */
html[data-bp~="sm-and-down"] .r-det-videos__actions {
  opacity: 1;
}

.r-det-videos__owner {
  position: absolute;
  top: 6px;
  left: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: calc(100% - 12px);
  padding: 2px 8px 2px 2px;
  border-radius: 999px;
  background: var(--r-color-overlay-scrim-strong);
  color: var(--r-color-overlay-fg);
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
}
.r-det-videos__owner span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-det-videos__badge {
  position: absolute;
  top: 6px;
  left: 6px;
}
</style>
