#!/bin/bash
# =============================================================================
# QwenPaw 升级脚本 - 一键同步官方更新并保留本地 MemOS 集成修改
# =============================================================================
# 用法: ./scripts/upgrade_qwenpaw.sh [options]
#
# 选项:
#   --skip-build    只同步代码，不构建镜像
#   --dry-run       预演模式，不执行实际操作
#   --help          显示帮助信息
#
# 作者: zhangbo6248
# 日期: 2026-05-07
# =============================================================================

set -e

# ─────────────────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────────────────
IMAGE_NAME="zhangbo6248/qwenpaw"
VERSION=$(date +%Y%m%d)-memos
PATCH_FILE="/tmp/qwenpaw_local_changes.patch"
SKIP_BUILD=false
DRY_RUN=false

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─────────────────────────────────────────────────────────────────────────────
# 帮助信息
# ─────────────────────────────────────────────────────────────────────────────
show_help() {
    echo "QwenPaw 升级脚本"
    echo ""
    echo "用法: $0 [options]"
    echo ""
    echo "选项:"
    echo "  --skip-build    只同步代码，不构建 Docker 镜像"
    echo "  --dry-run       预演模式，只显示将要执行的操作"
    echo "  --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整升级流程"
    echo "  $0 --skip-build       # 只同步代码"
    echo "  $0 --dry-run          # 预演模式"
}

# ─────────────────────────────────────────────────────────────────────────────
# 解析参数
# ─────────────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $1"
    else
        eval "$1"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 检查环境
# ─────────────────────────────────────────────────────────────────────────────
check_environment() {
    log_info "检查环境..."
    
    # 检查是否在 Git 仓库中
    if [ ! -d ".git" ]; then
        log_error "当前目录不是 Git 仓库"
        exit 1
    fi
    
    # 检查 upstream 配置
    if ! git remote | grep -q "upstream"; then
        log_error "未配置 upstream 远程仓库"
        log_info "请运行: git remote add upstream https://github.com/agentscope-ai/QwenPaw.git"
        exit 1
    fi
    
    # 检查是否有未提交的修改
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "有未提交的修改，将在升级前保存到 patch 文件"
    fi
    
    log_success "环境检查通过"
}

# ─────────────────────────────────────────────────────────────────────────────
# 步骤 1: 保存本地修改
# ─────────────────────────────────────────────────────────────────────────────
save_local_changes() {
    log_info "步骤 1/5: 保存本地修改..."
    
    if [ -n "$(git status --porcelain)" ]; then
        run_cmd "git add -A"
        run_cmd "git diff --staged > $PATCH_FILE"
        log_success "本地修改已保存到: $PATCH_FILE"
    else
        log_info "没有本地修改需要保存"
        run_cmd "touch $PATCH_FILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 步骤 2: 同步官方代码
# ─────────────────────────────────────────────────────────────────────────────
sync_upstream() {
    log_info "步骤 2/5: 同步官方代码..."
    
    run_cmd "git fetch upstream"
    
    # 检查是否有新的提交
    LOCAL_HEAD=$(git rev-parse HEAD)
    UPSTREAM_HEAD=$(git rev-parse upstream/main)
    
    if [ "$LOCAL_HEAD" = "$UPSTREAM_HEAD" ]; then
        log_info "已是最新版本，无需同步"
        return
    fi
    
    log_info "发现新版本:"
    git log HEAD..upstream/main --oneline | head -10
    
    # 尝试合并
    if [ "$DRY_RUN" = false ]; then
        git merge upstream/main --no-edit || {
            log_error "合并失败，请手动解决冲突后继续"
            log_info "解决冲突后运行: git add . && git commit"
            exit 1
        }
    else
        log_info "[DRY-RUN] 将执行: git merge upstream/main"
    fi
    
    log_success "官方代码同步完成"
}

# ─────────────────────────────────────────────────────────────────────────────
# 步骤 3: 重新应用本地修改
# ─────────────────────────────────────────────────────────────────────────────
apply_local_changes() {
    log_info "步骤 3/5: 重新应用本地修改..."
    
    if [ ! -s "$PATCH_FILE" ]; then
        log_info "没有本地修改需要应用"
        return
    fi
    
    if [ "$DRY_RUN" = false ]; then
        if git apply "$PATCH_FILE" 2>/dev/null; then
            log_success "本地修改已成功应用"
        else
            log_warning "部分修改不兼容，尝试三路合并..."
            if git apply --3way "$PATCH_FILE" 2>/dev/null; then
                log_success "通过三路合并成功应用修改"
            else
                log_error "修改应用失败，请手动检查"
                log_info "Patch 文件位置: $PATCH_FILE"
                log_info "手动应用: git apply $PATCH_FILE"
                exit 1
            fi
        fi
    else
        log_info "[DRY-RUN] 将执行: git apply $PATCH_FILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 步骤 4: 构建镜像
# ─────────────────────────────────────────────────────────────────────────────
build_image() {
    if [ "$SKIP_BUILD" = true ]; then
        log_info "步骤 4/5: 跳过镜像构建 (--skip-build)"
        return
    fi
    
    log_info "步骤 4/5: 构建 Docker 镜像..."
    
    FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"
    
    if [ "$DRY_RUN" = false ]; then
        docker build -t "$FULL_IMAGE_NAME" -f deploy/Dockerfile .
        log_success "镜像构建完成: $FULL_IMAGE_NAME"
    else
        log_info "[DRY-RUN] 将执行: docker build -t $FULL_IMAGE_NAME -f deploy/Dockerfile ."
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 步骤 5: 推送镜像（可选）
# ─────────────────────────────────────────────────────────────────────────────
push_image() {
    if [ "$SKIP_BUILD" = true ]; then
        log_info "步骤 5/5: 跳过镜像推送 (--skip-build)"
        return
    fi
    
    log_info "步骤 5/5: 推送镜像到仓库..."
    
    if [ "$DRY_RUN" = false ]; then
        read -p "是否推送镜像到 Docker Hub? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker push "${IMAGE_NAME}:${VERSION}"
            log_success "镜像已推送: ${IMAGE_NAME}:${VERSION}"
        else
            log_info "跳过推送，镜像仅保存在本地"
        fi
    else
        log_info "[DRY-RUN] 将询问是否推送镜像"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# 完成
# ─────────────────────────────────────────────────────────────────────────────
show_summary() {
    echo ""
    echo "========================================"
    echo -e "${GREEN}✅ QwenPaw 升级完成！${NC}"
    echo "========================================"
    echo ""
    echo "镜像版本: ${IMAGE_NAME}:${VERSION}"
    echo ""
    echo "后续步骤:"
    echo "  1. 测试新镜像:"
    echo "     docker-compose -f deploy/docker-compose.yml up -d"
    echo ""
    echo "  2. 查看日志:"
    echo "     docker-compose -f deploy/docker-compose.yml logs -f"
    echo ""
    echo "  3. 回滚（如果需要）:"
    echo "     docker pull ${IMAGE_NAME}:<旧版本>"
    echo "     docker-compose -f deploy/docker-compose.yml up -d"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo "========================================"
    echo "  QwenPaw 升级脚本"
    echo "  版本: $VERSION"
    echo "========================================"
    echo ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "预演模式 (DRY-RUN)"
        echo ""
    fi
    
    check_environment
    save_local_changes
    sync_upstream
    apply_local_changes
    build_image
    push_image
    show_summary
}

main
