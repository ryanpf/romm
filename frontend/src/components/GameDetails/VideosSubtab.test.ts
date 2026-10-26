import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserVideoSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import VideosSubtab from "./VideosSubtab.vue";

const { uploadGalleryVideos, refetchRom } = vi.hoisted(() => ({
  uploadGalleryVideos: vi.fn(),
  refetchRom: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("@/services/api/video", () => ({
  default: {
    uploadGalleryVideos,
    deleteVideo: vi.fn(),
    setVideoVisibility: vi.fn(),
  },
}));

vi.mock("@/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom }),
}));

vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

const USER_ID = 3;

function video(
  id: number,
  userId: number,
  overrides: Partial<UserVideoSchema> = {},
): UserVideoSchema {
  return {
    id,
    rom_id: 1,
    user_id: userId,
    file_name: `clip${id}.mp4`,
    file_name_no_tags: `clip${id}`,
    file_name_no_ext: `clip${id}`,
    file_extension: "mp4",
    file_path: "users/x/videos/n64/1",
    file_size_bytes: 10,
    full_path: `users/x/videos/n64/1/clip${id}.mp4`,
    download_path: `/api/videos/${id}/content`,
    missing_from_fs: false,
    created_at: "2026-10-26T00:00:00Z",
    updated_at: "2026-10-26T00:00:00Z",
    is_public: false,
    screenshot: null,
    username: `user${userId}`,
    ...overrides,
  };
}

const VideosTab = {
  props: { videos: Array, editable: Boolean },
  template: `<div class="videos" :data-editable="editable">
    <span v-for="v in videos" :key="v.id" class="video"
      :data-poster="v.posterUrl" :data-owner="v.username">{{ v.id }}</span>
  </div>`,
};
const RDropzone = {
  emits: ["files"],
  template: `<div class="dropzone"><slot /></div>`,
};

function mountSubtab(videos: UserVideoSchema[]) {
  return mount(VideosSubtab, {
    props: { rom: detailedRomFixture({ id: 1, all_user_videos: videos }) },
    global: {
      stubs: {
        VideosTab,
        RDropzone,
        RBtn: true,
        ScreenshotEditDialog: true,
      },
    },
  });
}

describe("VideosSubtab", () => {
  beforeEach(() => {
    storeAuth().setCurrentUser(userFixture({ id: USER_ID }));
    uploadGalleryVideos.mockReset();
    refetchRom.mockReset();
  });

  it("splits the user's own videos from the community's", () => {
    const poster = { download_path: "/api/screenshots/9/content" };
    const wrapper = mountSubtab([
      video(1, USER_ID, {
        screenshot: poster as UserVideoSchema["screenshot"],
      }),
      video(2, 7, { is_public: true }),
    ]);

    const [mine, community] = wrapper.findAll(".videos");
    expect(mine!.attributes("data-editable")).toBe("true");
    expect(mine!.find(".video").attributes("data-poster")).toBe(
      poster.download_path,
    );
    expect(mine!.find(".video").attributes("data-owner")).toBeUndefined();
    expect(community!.find(".video").attributes("data-owner")).toBe("user7");
  });

  it("offers the upload dropzone with no videos of its own", () => {
    const wrapper = mountSubtab([video(2, 7, { is_public: true })]);

    expect(wrapper.findAll(".videos")).toHaveLength(1);
    expect(wrapper.find(".dropzone").exists()).toBe(true);
  });

  it("uploads dropped files and refetches the rom", async () => {
    uploadGalleryVideos.mockResolvedValue([
      { status: "fulfilled", value: video(5, USER_ID) },
    ]);
    const wrapper = mountSubtab([]);
    const file = new File(["x"], "clip.mp4", { type: "video/mp4" });

    wrapper.findComponent(RDropzone).vm.$emit("files", [file]);
    await flushPromises();

    expect(uploadGalleryVideos).toHaveBeenCalledWith({
      romId: 1,
      filesToUpload: [file],
    });
    expect(refetchRom).toHaveBeenCalledWith(1);
  });
});
