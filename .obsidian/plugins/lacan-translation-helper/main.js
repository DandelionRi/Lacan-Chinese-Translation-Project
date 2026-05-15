const Obsidian = require("obsidian");
const { Notice, Plugin, PluginSettingTab, Setting, TFile, normalizePath } = Obsidian;
const ObsidianBasesView = Obsidian.BasesView || class {};

const LESSON_FILE_RE = /^(?:Leçon|Lecon|lesson)-(\d+)\.md$/i;
const ORIGINAL_PATH_RE = /^texts\/([^/]+)\/original\/((?:Leçon|Lecon|lesson)-\d+\.md)$/i;
const TRANSLATION_PATH_RE = /^texts\/([^/]+)\/translation\/((?:Leçon|Lecon|lesson)-\d+\.md)$/i;
const ID_RE = /<!--\s*id:\s*([^>\s]+)\s*-->/g;
const SEGMENT_ID_RE = /\bs\d+b?-\d+-(\d+)\b/gi;
const SEMINAR_RE = /<!--\s*seminar:\s*([^>\s]+)\s*-->/i;
const LESSON_RE = /<!--\s*lesson:\s*([^>\s]+)\s*-->/i;
const UNTRANSLATED_RE = /<!--\s*untranslated\s*-->/gi;
const LACAN_LESSON_LIST_VIEW_TYPE = "lacan-lesson-list";
const DEFAULT_REPOSITORY_URL = "https://github.com/Kotoba-Rin/Lacan-Chinese-Translation-Project.git";

const DEFAULT_SETTINGS = {
  mode: "reader",
  repositoryUrl: DEFAULT_REPOSITORY_URL,
  repositoryBranch: "main",
  upstreamLocalBranch: "lacan-upstream/main",
  autoSyncOnStartup: false,
  forks: [],
};

module.exports = class LacanTranslationHelper extends Plugin {
  async onload() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.settings.forks = Array.isArray(this.settings.forks) ? this.settings.forks : [];
    this.progressTimers = new Map();
    this.activeComparisonForks = new Set();
    this.compareRenderTimer = null;

    this.addSettingTab(new LacanTranslationHelperSettingTab(this.app, this));

    this.registerEvent(
      this.app.vault.on("create", (file) => {
        this.handleCreatedFile(file);
      })
    );

    this.registerEvent(
      this.app.vault.on("modify", (file) => {
        this.handleModifiedFile(file);
      })
    );

    this.registerEvent(
      this.app.workspace.on("file-menu", (menu, file) => {
        this.addFileMenuItems(menu, file);
      })
    );

    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => {
        this.scheduleComparisonRender();
      })
    );

    this.registerEvent(
      this.app.workspace.on("layout-change", () => {
        this.scheduleComparisonRender();
      })
    );

    this.registerEvent(
      this.app.workspace.on("file-open", () => {
        this.scheduleComparisonRender();
      })
    );

    this.registerProjectBasesView();

    this.addCommand({
      id: "create-translation-skeleton-from-active-file",
      name: "Create translation skeleton from active lesson",
      callback: () =>
        this.runWithNotice(
          () => this.createSkeletonFromActiveFile(),
          "译文骨架生成失败"
        ),
    });

    this.addCommand({
      id: "update-all-translation-progress",
      name: "Update translation progress for all lessons",
      callback: () =>
        this.runWithNotice(
          () => this.updateAllTranslationProgress(),
          "翻译进度更新失败"
        ),
    });

    this.addCommand({
      id: "sync-configured-github-repositories",
      name: "Sync configured GitHub repositories",
      callback: () =>
        this.runWithNotice(
          () => this.syncConfiguredRepositories({ notify: true }),
          "Git 同步失败"
        ),
    });

    this.scheduleComparisonRender();

    if (this.settings.autoSyncOnStartup) {
      window.setTimeout(() => {
        this.runWithNotice(
          () => this.syncConfiguredRepositories({ notify: true }),
          "Git 自动同步失败"
        );
      }, 1500);
    }
  }

  onunload() {
    for (const timer of this.progressTimers.values()) {
      window.clearTimeout(timer);
    }
    this.progressTimers.clear();

    if (this.compareRenderTimer) {
      window.clearTimeout(this.compareRenderTimer);
      this.compareRenderTimer = null;
    }
  }

  registerProjectBasesView() {
    if (typeof this.registerBasesView !== "function" || !Obsidian.BasesView) {
      console.warn("Lacan Translation Helper: Obsidian Bases view API is unavailable.");
      return;
    }

    this.registerBasesView(LACAN_LESSON_LIST_VIEW_TYPE, {
      name: "Lacan Lesson List",
      icon: "list-tree",
      factory: (controller, containerEl) => new LacanLessonListBasesView(controller, containerEl, this),
    });
  }

  async handleCreatedFile(file) {
    if (!(file instanceof TFile) || !this.isTranslationLessonPath(file.path)) {
      return;
    }

    // Let Obsidian finish the unresolved-link creation write before we inspect it.
    window.setTimeout(async () => {
      await this.runWithNotice(
        () => this.fillTranslationIfEmpty(file, { openAfterCreate: false, notify: false, updateProgress: true }),
        "译文骨架生成失败"
      );
    }, 100);
  }

  handleModifiedFile(file) {
    if (!(file instanceof TFile) || !this.isTranslationLessonPath(file.path)) {
      return;
    }

    this.scheduleProgressUpdate(file.path);
  }

  addFileMenuItems(menu, file) {
    if (!(file instanceof TFile)) {
      return;
    }

    if (this.isOriginalLessonPath(file.path)) {
      menu.addItem((item) => {
        item
          .setTitle("生成译文骨架")
          .setIcon("languages")
          .onClick(async () => {
            await this.runWithNotice(
              () => this.createTranslationForOriginal(file, { openAfterCreate: true, notify: true }),
              "译文骨架生成失败"
            );
          });
      });
      return;
    }

    if (this.isTranslationLessonPath(file.path)) {
      menu.addItem((item) => {
        item
          .setTitle("为空译文填充分段骨架")
          .setIcon("list-plus")
          .onClick(async () => {
            await this.runWithNotice(
              () => this.fillTranslationIfEmpty(file, { openAfterCreate: true, notify: true }),
              "译文骨架生成失败"
            );
          });
      });
    }
  }

  async createSkeletonFromActiveFile() {
    const file = this.app.workspace.getActiveFile();
    if (!(file instanceof TFile)) {
      new Notice("没有活动的课文文件。");
      return;
    }

    if (this.isOriginalLessonPath(file.path)) {
      await this.createTranslationForOriginal(file, { openAfterCreate: true, notify: true, updateProgress: true });
      return;
    }

    if (this.isTranslationLessonPath(file.path)) {
      await this.fillTranslationIfEmpty(file, {
        openAfterCreate: true,
        notify: true,
        notifyExisting: true,
        updateProgress: true,
      });
      return;
    }

    new Notice("当前文件不是 texts/*/original 或 texts/*/translation 下的 Leçon 文件。");
  }

  async runWithNotice(action, prefix) {
    try {
      return await action();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Lacan Translation Helper: ${prefix}`, error);
      new Notice(`${prefix}：${message}`);
      return null;
    }
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async syncConfiguredRepositories({ notify = false } = {}) {
    if (this.settings.mode === "reader") {
      await this.syncReaderRepository();
    } else {
      await this.syncEditorRepository();
      for (const fork of this.settings.forks) {
        await this.syncForkRepository(fork);
      }
    }

    if (notify) {
      new Notice("Git 同步完成。");
    }
  }

  async syncReaderRepository() {
    const url = this.settings.repositoryUrl?.trim();
    const branch = this.settings.repositoryBranch?.trim() || "main";
    if (!url) {
      throw new Error("尚未配置 Lacan-Chinese-Translation-Project 仓库地址。");
    }

    await this.execGit(["pull", "--ff-only", url, branch]);
  }

  async syncEditorRepository() {
    const url = this.settings.repositoryUrl?.trim();
    const branch = this.settings.repositoryBranch?.trim() || "main";
    const localBranch = this.settings.upstreamLocalBranch?.trim() || "lacan-upstream/main";
    if (!url) {
      throw new Error("尚未配置 Lacan-Chinese-Translation-Project 仓库地址。");
    }

    await this.fetchRepositoryToLocalBranch(url, branch, localBranch);
  }

  async syncForkRepository(fork) {
    if (!fork?.enabled) {
      return;
    }
    const url = fork.url?.trim();
    const branch = fork.remoteBranch?.trim() || "main";
    const localBranch = fork.localBranch?.trim();
    if (!url || !localBranch) {
      throw new Error(`fork 配置不完整：${fork.name || url || "未命名 fork"}`);
    }

    await this.fetchRepositoryToLocalBranch(url, branch, localBranch);
  }

  async fetchRepositoryToLocalBranch(url, remoteBranch, localBranch) {
    await this.execGit(["check-ref-format", "--branch", localBranch]);
    const currentBranch = (await this.execGit(["branch", "--show-current"])).trim();
    if (currentBranch && currentBranch === localBranch) {
      throw new Error(`当前分支是 ${localBranch}，为避免覆盖当前分支，已取消同步。`);
    }

    await this.execGit(["fetch", "--no-tags", url, `+${remoteBranch}:refs/heads/${localBranch}`]);
  }

  async execGit(args) {
    const cwd = this.getVaultBasePath();
    const childProcess = require("child_process");

    return new Promise((resolve, reject) => {
      childProcess.execFile("git", args, { cwd }, (error, stdout, stderr) => {
        if (error) {
          const detail = String(stderr || stdout || error.message).trim();
          reject(new Error(detail || error.message));
          return;
        }
        resolve(String(stdout || ""));
      });
    });
  }

  getVaultBasePath() {
    const adapter = this.app.vault.adapter;
    if (typeof adapter.getBasePath === "function") {
      return adapter.getBasePath();
    }
    throw new Error("Git 功能需要 Obsidian 桌面端本地 vault。");
  }

  scheduleComparisonRender(delay = 150) {
    if (this.compareRenderTimer) {
      window.clearTimeout(this.compareRenderTimer);
    }
    this.compareRenderTimer = window.setTimeout(() => {
      this.compareRenderTimer = null;
      this.renderComparisonToolbar();
    }, delay);
  }

  renderComparisonToolbar() {
    const file = this.app.workspace.getActiveFile();
    if (
      this.settings.mode !== "editer"
      || !(file instanceof TFile)
      || !file.path.startsWith("texts/")
      || file.extension !== "md"
    ) {
      this.removeComparisonToolbars();
      return;
    }

    const view = Obsidian.MarkdownView
      ? this.app.workspace.getActiveViewOfType(Obsidian.MarkdownView)
      : this.app.workspace.activeLeaf?.view;
    if (!view?.containerEl) {
      return;
    }

    const contentEl = view.containerEl.querySelector(".view-content");
    if (!contentEl) {
      return;
    }

    let toolbarEl = contentEl.querySelector(":scope > .lacan-compare-toolbar");
    if (!toolbarEl) {
      toolbarEl = contentEl.createDiv("lacan-compare-toolbar");
      contentEl.prepend(toolbarEl);
    }

    toolbarEl.empty();
    const titleEl = toolbarEl.createSpan({
      cls: "lacan-compare-toolbar-title",
      text: "Fork 对照",
    });
    titleEl.setAttribute("aria-label", "开启或关闭 fork 仓库内容对照");

    const forks = this.settings.forks.filter((fork) => fork.enabled && fork.localBranch);

    if (forks.length === 0) {
      toolbarEl.createSpan({
        cls: "lacan-compare-empty",
        text: "未配置可对照 fork",
      });
      this.renderComparisonPanels(toolbarEl, file);
      return;
    }

    for (const fork of forks) {
      const active = this.activeComparisonForks.has(fork.id);
      const button = toolbarEl.createEl("button", {
        cls: active ? "lacan-compare-button is-active" : "lacan-compare-button",
        text: active ? `关闭 ${fork.name || fork.localBranch}` : `对照 ${fork.name || fork.localBranch}`,
      });
      button.addEventListener("click", async () => {
        if (active) {
          this.activeComparisonForks.delete(fork.id);
        } else {
          this.activeComparisonForks.add(fork.id);
        }
        this.renderComparisonToolbar();
      });
    }

    this.renderComparisonPanels(toolbarEl, file);
  }

  removeComparisonToolbars() {
    document.querySelectorAll(".lacan-compare-toolbar").forEach((element) => element.remove());
  }

  renderComparisonPanels(toolbarEl, file) {
    const existingPanels = toolbarEl.querySelector(".lacan-compare-panels");
    existingPanels?.remove();

    const activeForks = this.settings.forks.filter((fork) =>
      fork.enabled && fork.localBranch && this.activeComparisonForks.has(fork.id)
    );
    if (activeForks.length === 0) {
      return;
    }

    const panelsEl = toolbarEl.createDiv("lacan-compare-panels");
    for (const fork of activeForks) {
      const panelEl = panelsEl.createDiv("lacan-compare-panel");
      panelEl.createDiv({
        cls: "lacan-compare-panel-title",
        text: `${fork.name || fork.localBranch} · ${fork.localBranch}`,
      });
      const contentEl = panelEl.createEl("pre", {
        cls: "lacan-compare-content",
        text: "加载中...",
      });

      this.loadForkFileContent(fork.localBranch, file.path)
        .then((content) => {
          contentEl.setText(content || "[该 fork 中没有对应内容]");
        })
        .catch((error) => {
          contentEl.setText(`无法读取 fork 内容：${error.message}`);
        });
    }
  }

  async loadForkFileContent(branch, path) {
    return this.execGit(["show", `${branch}:${path}`]);
  }

  async createTranslationForOriginal(originalFile, options = {}) {
    const paths = this.pathsFromOriginal(originalFile.path);
    if (!paths) {
      throw new Error("不是有效的原文课文路径。");
    }

    const existing = this.app.vault.getAbstractFileByPath(paths.translationPath);
    if (existing instanceof TFile) {
      await this.fillTranslationIfEmpty(existing, options);
      return existing;
    }

    const originalText = await this.app.vault.read(originalFile);
    const skeleton = this.buildSkeleton(originalFile.path, originalText);
    await this.ensureFolder(paths.translationFolder);
    const created = await this.app.vault.create(paths.translationPath, skeleton);
    if (options.updateProgress !== false) {
      await this.updateTranslationProgress(created);
    }

    if (options.openAfterCreate) {
      await this.openFile(created);
    }
    if (options.notify) {
      new Notice(`已创建译文骨架：${paths.translationPath}`);
    }
    return created;
  }

  async fillTranslationIfEmpty(translationFile, options = {}) {
    const paths = this.pathsFromTranslation(translationFile.path);
    if (!paths) {
      throw new Error("不是有效的译文课文路径。");
    }

    const currentText = await this.app.vault.read(translationFile);
    if (currentText.trim().length > 0) {
      if (options.updateProgress) {
        await this.updateTranslationProgress(translationFile);
      }
      if (options.openAfterCreate) {
        await this.openFile(translationFile);
      }
      if (options.notify && options.notifyExisting) {
        new Notice("译文文件已有内容，未覆盖。");
      }
      return translationFile;
    }

    const originalFile = this.app.vault.getAbstractFileByPath(paths.originalPath);
    if (!(originalFile instanceof TFile)) {
      throw new Error(`找不到对应原文：${paths.originalPath}`);
    }

    const originalText = await this.app.vault.read(originalFile);
    const skeleton = this.buildSkeleton(originalFile.path, originalText);
    await this.app.vault.modify(translationFile, skeleton);
    if (options.updateProgress !== false) {
      await this.updateTranslationProgress(translationFile);
    }

    if (options.openAfterCreate) {
      await this.openFile(translationFile);
    }
    if (options.notify) {
      new Notice(`已填充译文骨架：${translationFile.path}`);
    }
    return translationFile;
  }

  scheduleProgressUpdate(path) {
    const normalized = normalizePath(path);
    const existing = this.progressTimers.get(normalized);
    if (existing) {
      window.clearTimeout(existing);
    }

    const timer = window.setTimeout(async () => {
      this.progressTimers.delete(normalized);
      await this.runWithNotice(
        () => this.updateTranslationProgressByPath(normalized),
        "翻译进度更新失败"
      );
    }, 500);
    this.progressTimers.set(normalized, timer);
  }

  async updateTranslationProgressByPath(path) {
    const file = this.app.vault.getAbstractFileByPath(path);
    if (!(file instanceof TFile)) {
      return null;
    }
    return this.updateTranslationProgress(file);
  }

  async updateAllTranslationProgress() {
    const files = this.app.vault
      .getMarkdownFiles()
      .filter((file) => this.isTranslationLessonPath(file.path));

    let updated = 0;
    for (const file of files) {
      const changed = await this.updateTranslationProgress(file);
      if (changed) {
        updated += 1;
      }
    }

    new Notice(`已更新 ${updated}/${files.length} 个译文进度。`);
  }

  async updateTranslationProgress(translationFile) {
    const paths = this.pathsFromTranslation(translationFile.path);
    if (!paths) {
      throw new Error("不是有效的译文课文路径。");
    }

    const translationText = await this.app.vault.read(translationFile);
    const originalFile = this.app.vault.getAbstractFileByPath(paths.originalPath);
    const originalText = originalFile instanceof TFile ? await this.app.vault.read(originalFile) : "";
    const stats = this.calculateTranslationProgress(translationText, originalText);
    const values = {
      translation_progress: stats.progress,
      translation_progress_label: stats.progressLabel,
      untranslated_count: stats.untranslatedCount,
      max_segment_id: stats.maxSegmentId,
    };

    const currentFrontmatter = this.app.metadataCache.getFileCache(translationFile)?.frontmatter || {};
    if (!this.frontmatterNeedsUpdate(currentFrontmatter, values)) {
      return false;
    }

    await this.app.fileManager.processFrontMatter(translationFile, (frontmatter) => {
      for (const [key, value] of Object.entries(values)) {
        frontmatter[key] = value;
      }
    });

    return true;
  }

  calculateTranslationProgress(translationText, originalText = "") {
    const untranslatedCount = this.countMatches(translationText, UNTRANSLATED_RE);
    const maxSegmentId = Math.max(
      this.maxSegmentIdNumber(originalText),
      this.maxSegmentIdNumber(translationText)
    );
    const ratio = maxSegmentId > 0 ? 1 - untranslatedCount / maxSegmentId : 0;
    const progress = Math.max(0, Math.min(100, ratio * 100));
    const rounded = Math.round(progress * 100) / 100;

    return {
      untranslatedCount,
      maxSegmentId,
      progress: rounded,
      progressLabel: `${rounded.toFixed(2)}%`,
    };
  }

  countMatches(text, regexp) {
    regexp.lastIndex = 0;
    let count = 0;
    while (regexp.exec(text) !== null) {
      count += 1;
    }
    return count;
  }

  maxSegmentIdNumber(text) {
    SEGMENT_ID_RE.lastIndex = 0;
    let max = 0;
    let match;
    while ((match = SEGMENT_ID_RE.exec(text)) !== null) {
      max = Math.max(max, Number(match[1]));
    }
    return max;
  }

  frontmatterNeedsUpdate(frontmatter, values) {
    return Object.entries(values).some(([key, value]) => frontmatter[key] !== value);
  }

  buildSkeleton(originalPath, originalText) {
    const title = this.extractTitle(originalText) || this.fallbackTitle(originalPath);
    const seminar = this.extractCommentValue(originalText, SEMINAR_RE) || this.seminarFromPath(originalPath);
    const lesson = this.extractCommentValue(originalText, LESSON_RE) || this.lessonFromPath(originalPath);
    const ids = this.extractParagraphIds(originalText);

    if (ids.length === 0) {
      throw new Error("原文中没有找到分段 ID。");
    }

    const lines = [
      title,
      "",
      `<!-- source-original: ${originalPath} -->`,
      "",
      `<!-- seminar: ${seminar} -->`,
      "",
      `<!-- lesson: ${lesson} -->`,
      "",
    ];

    for (const id of ids) {
      lines.push(`<!-- id: ${id} -->`, "", "<!-- untranslated -->", "");
    }

    return `${lines.join("\n").replace(/\n+$/, "")}\n`;
  }

  extractTitle(text) {
    for (const line of text.split(/\r?\n/)) {
      if (line.startsWith("#")) {
        return line.trim();
      }
      if (line.trim()) {
        break;
      }
    }
    return "";
  }

  extractCommentValue(text, regexp) {
    const match = regexp.exec(text);
    return match ? match[1].trim() : "";
  }

  extractParagraphIds(text) {
    const ids = [];
    const seen = new Set();
    let match;
    while ((match = ID_RE.exec(text)) !== null) {
      const id = match[1].trim();
      if (!seen.has(id)) {
        ids.push(id);
        seen.add(id);
      }
    }
    return ids;
  }

  fallbackTitle(path) {
    const lesson = this.lessonFromPath(path);
    return `# Leçon ${lesson}`;
  }

  seminarFromPath(path) {
    const match = path.match(/^texts\/([^/]+)\//);
    return match ? match[1].split("-")[0].toLowerCase() : "";
  }

  lessonFromPath(path) {
    const name = path.split("/").pop() || "";
    const match = name.match(LESSON_FILE_RE);
    return match ? match[1] : "";
  }

  isOriginalLessonPath(path) {
    return ORIGINAL_PATH_RE.test(normalizePath(path));
  }

  isTranslationLessonPath(path) {
    return TRANSLATION_PATH_RE.test(normalizePath(path));
  }

  pathsFromOriginal(path) {
    const normalized = normalizePath(path);
    const match = normalized.match(ORIGINAL_PATH_RE);
    if (!match) {
      return null;
    }
    const translationPath = normalized.replace("/original/", "/translation/");
    return {
      originalPath: normalized,
      translationPath,
      translationFolder: translationPath.split("/").slice(0, -1).join("/"),
    };
  }

  pathsFromTranslation(path) {
    const normalized = normalizePath(path);
    const match = normalized.match(TRANSLATION_PATH_RE);
    if (!match) {
      return null;
    }
    const originalPath = normalized.replace("/translation/", "/original/");
    return {
      originalPath,
      translationPath: normalized,
      translationFolder: normalized.split("/").slice(0, -1).join("/"),
    };
  }

  async ensureFolder(folderPath) {
    const parts = normalizePath(folderPath).split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      if (!this.app.vault.getAbstractFileByPath(current)) {
        await this.app.vault.createFolder(current);
      }
    }
  }

  async openFile(file) {
    await this.app.workspace.getLeaf(false).openFile(file);
  }
};

class LacanTranslationHelperSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Lacan Translation Helper" });

    new Setting(containerEl)
      .setName("模式")
      .setDesc("Reader 会把当前分支快进同步到上游；Editer 只 fetch 到对照分支，不切换、不覆盖当前分支。")
      .addDropdown((dropdown) => {
        dropdown
          .addOption("reader", "Reader")
          .addOption("editer", "Editer")
          .setValue(this.plugin.settings.mode)
          .onChange(async (value) => {
            this.plugin.settings.mode = value;
            await this.plugin.saveSettings();
            this.plugin.scheduleComparisonRender();
            this.display();
          });
      });

    new Setting(containerEl)
      .setName("Lacan-Chinese-Translation-Project 仓库地址")
      .setDesc("Reader 模式用于 git pull；Editer 模式用于 fetch 到上游对照分支。")
      .addText((text) => {
        text
          .setPlaceholder(DEFAULT_REPOSITORY_URL)
          .setValue(this.plugin.settings.repositoryUrl || "")
          .onChange(async (value) => {
            this.plugin.settings.repositoryUrl = value.trim();
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("上游分支")
      .setDesc("通常是 main。")
      .addText((text) => {
        text
          .setPlaceholder("main")
          .setValue(this.plugin.settings.repositoryBranch || "main")
          .onChange(async (value) => {
            this.plugin.settings.repositoryBranch = value.trim() || "main";
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("Editer 模式上游本地分支")
      .setDesc("Editer 模式会把上游 fetch 到这个本地分支；如果它是当前分支，同步会被拒绝。")
      .addText((text) => {
        text
          .setPlaceholder("lacan-upstream/main")
          .setValue(this.plugin.settings.upstreamLocalBranch || "lacan-upstream/main")
          .onChange(async (value) => {
            this.plugin.settings.upstreamLocalBranch = value.trim() || "lacan-upstream/main";
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("启动时自动同步")
      .setDesc("Reader 模式执行 pull --ff-only；Editer 模式执行 fetch 到配置的对照分支。")
      .addToggle((toggle) => {
        toggle
          .setValue(Boolean(this.plugin.settings.autoSyncOnStartup))
          .onChange(async (value) => {
            this.plugin.settings.autoSyncOnStartup = value;
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("立即同步")
      .setDesc("按当前模式同步上游和已启用 fork。")
      .addButton((button) => {
        button
          .setButtonText("同步")
          .setCta()
          .onClick(async () => {
            await this.plugin.runWithNotice(
              () => this.plugin.syncConfiguredRepositories({ notify: true }),
              "Git 同步失败"
            );
          });
      });

    containerEl.createEl("h3", { text: "Fork 对照分支" });
    containerEl.createEl("p", {
      cls: "setting-item-description",
      text: "每个 fork 会 fetch 到独立本地分支。Editer 模式查看 texts 文件时，可用顶部按钮开启/关闭对应 fork 的文本对照。",
    });

    this.renderForkSettings(containerEl);

    new Setting(containerEl)
      .setName("添加 fork")
      .setDesc("添加一个新的 fork 仓库配置。")
      .addButton((button) => {
        button
          .setButtonText("添加")
          .onClick(async () => {
            const nextIndex = this.plugin.settings.forks.length + 1;
            this.plugin.settings.forks.push({
              id: this.createForkId(),
              name: `fork-${nextIndex}`,
              url: "",
              remoteBranch: "main",
              localBranch: `lacan-fork/fork-${nextIndex}`,
              enabled: true,
            });
            await this.plugin.saveSettings();
            this.display();
          });
      });
  }

  renderForkSettings(containerEl) {
    for (const fork of this.plugin.settings.forks) {
      const sectionEl = containerEl.createDiv("lacan-settings-fork");
      sectionEl.createEl("h4", { text: fork.name || fork.localBranch || "未命名 fork" });

      new Setting(sectionEl)
        .setName("启用")
        .setDesc("启用后会参与 Editer 模式同步，并显示为文本对照按钮。")
        .addToggle((toggle) => {
          toggle
            .setValue(Boolean(fork.enabled))
            .onChange(async (value) => {
              fork.enabled = value;
              await this.plugin.saveSettings();
              this.plugin.scheduleComparisonRender();
            });
        });

      new Setting(sectionEl)
        .setName("名称")
        .addText((text) => {
          text
            .setPlaceholder("fork 名称")
            .setValue(fork.name || "")
            .onChange(async (value) => {
              fork.name = value.trim();
              await this.plugin.saveSettings();
              this.plugin.scheduleComparisonRender();
            });
        });

      new Setting(sectionEl)
        .setName("仓库地址")
        .addText((text) => {
          text
            .setPlaceholder("https://github.com/user/Lacan-Chinese-Translation-Project.git")
            .setValue(fork.url || "")
            .onChange(async (value) => {
              fork.url = value.trim();
              await this.plugin.saveSettings();
            });
        });

      new Setting(sectionEl)
        .setName("远端分支")
        .addText((text) => {
          text
            .setPlaceholder("main")
            .setValue(fork.remoteBranch || "main")
            .onChange(async (value) => {
              fork.remoteBranch = value.trim() || "main";
              await this.plugin.saveSettings();
            });
        });

      new Setting(sectionEl)
        .setName("本地对照分支")
        .setDesc("不要设置为当前正在编辑的分支。同步时会更新这个分支指针。")
        .addText((text) => {
          text
            .setPlaceholder("lacan-fork/user-main")
            .setValue(fork.localBranch || "")
            .onChange(async (value) => {
              fork.localBranch = value.trim();
              await this.plugin.saveSettings();
              this.plugin.scheduleComparisonRender();
            });
        });

      new Setting(sectionEl)
        .setName("操作")
        .addButton((button) => {
          button
            .setButtonText("同步 fork")
            .onClick(async () => {
              await this.plugin.runWithNotice(
                async () => {
                  await this.plugin.syncForkRepository(fork);
                  new Notice(`已同步 fork：${fork.name || fork.localBranch}`);
                },
                "fork 同步失败"
              );
            });
        })
        .addButton((button) => {
          button
            .setButtonText("删除")
            .setWarning()
            .onClick(async () => {
              this.plugin.settings.forks = this.plugin.settings.forks.filter((item) => item.id !== fork.id);
              this.plugin.activeComparisonForks.delete(fork.id);
              await this.plugin.saveSettings();
              this.plugin.scheduleComparisonRender();
              this.display();
            });
        });
    }
  }

  createForkId() {
    return `fork-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }
}

class LacanLessonListBasesView extends ObsidianBasesView {
  constructor(controller, parentEl, plugin) {
    super(controller);
    this.plugin = plugin;
    this.containerEl = parentEl.createDiv("lacan-bases-list");
  }

  onDataUpdated() {
    this.containerEl.empty();
    const groups = this.data?.groupedData?.length
      ? this.data.groupedData
      : [{ entries: this.data?.entries || [] }];
    const mode = String(this.config?.get?.("mode") || "reader");

    for (const group of groups) {
      const entries = group.entries || [];
      const details = this.containerEl.createEl("details", {
        cls: "lacan-bases-group",
      });
      const summary = details.createEl("summary", {
        cls: "lacan-bases-group-summary",
      });

      summary.createSpan({
        cls: "lacan-bases-group-title",
        text: this.getGroupTitle(group),
      });
      summary.createSpan({
        cls: "lacan-bases-group-count",
        text: `${entries.length}`,
      });

      const listEl = details.createEl("ul", {
        cls: "lacan-bases-group-list",
      });

      for (const entry of entries) {
        this.renderEntry(listEl, entry, mode);
      }
    }
  }

  getGroupTitle(group) {
    const value = this.valueToString(group?.value);
    if (value && value !== "[object Object]") {
      return value;
    }

    const firstEntry = group.entries?.[0];
    return this.valueToString(firstEntry?.getValue?.("formula.seminarGroup")) || "未分组";
  }

  renderEntry(listEl, entry, mode) {
    const lessonTitle = this.valueToString(entry.getValue("formula.lessonTitle"));
    const originalPath = this.valueToString(entry.getValue("formula.originalPath"));
    const translationPath = this.valueToString(entry.getValue("formula.translationPath"));
    const progress = this.valueToString(entry.getValue("formula.translationProgressLabel")) || "0.00%";
    const untranslatedCount = this.valueToString(entry.getValue("formula.untranslatedCount"));
    const maxSegmentId = this.valueToString(entry.getValue("formula.maxSegmentId"));
    const translationFile = this.plugin.app.vault.getAbstractFileByPath(translationPath);

    const itemEl = listEl.createEl("li", {
      cls: "lacan-bases-entry",
    });
    const mainEl = itemEl.createDiv("lacan-bases-entry-main");

    mainEl.createSpan({
      cls: "lacan-bases-entry-title",
      text: lessonTitle,
    });
    this.createActionLink(mainEl, "原文", () => this.openOriginal(entry.file, originalPath));
    this.createActionLink(
      mainEl,
      translationFile instanceof TFile ? "译文" : "新建翻译",
      () => this.openOrCreateTranslation(entry.file, translationFile)
    );
    mainEl.createSpan({
      cls: "lacan-bases-progress",
      text: progress,
    });

    if (mode === "editer") {
      const metaEl = itemEl.createDiv("lacan-bases-entry-meta");
      metaEl.createSpan({ text: `原文：${originalPath}` });
      metaEl.createSpan({ text: `译文：${translationPath}` });
      metaEl.createSpan({ text: `未译：${untranslatedCount || 0}` });
      metaEl.createSpan({ text: `最大分段：${maxSegmentId || 0}` });
    }
  }

  createActionLink(parentEl, text, action) {
    const linkEl = parentEl.createEl("a", {
      cls: "lacan-bases-link",
      href: "#",
      text,
    });
    linkEl.addEventListener("click", async (event) => {
      event.preventDefault();
      await this.plugin.runWithNotice(action, "打开课文失败");
    });
  }

  async openOriginal(originalFile, originalPath) {
    if (originalFile instanceof TFile) {
      await this.plugin.openFile(originalFile);
      return;
    }

    const file = this.plugin.app.vault.getAbstractFileByPath(originalPath);
    if (file instanceof TFile) {
      await this.plugin.openFile(file);
    }
  }

  async openOrCreateTranslation(originalFile, translationFile) {
    if (translationFile instanceof TFile) {
      await this.plugin.openFile(translationFile);
      return;
    }

    if (!(originalFile instanceof TFile)) {
      throw new Error("找不到对应原文，无法创建译文。");
    }

    await this.plugin.createTranslationForOriginal(originalFile, {
      openAfterCreate: true,
      notify: true,
      updateProgress: true,
    });
  }

  valueToString(value) {
    if (!value || value.isEmpty?.()) {
      return "";
    }
    return String(value);
  }
}
