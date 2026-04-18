#!/bin/bash
# =================================================================
# Docker 镜像构建脚本 - 自动更新版本号并打 tag
# 用法: ./scripts/build_with_version.sh [patch|minor|major|current]
#   patch: 小版本号 (2.2.0 -> 2.2.1) 默认
#   minor: 中版本号 (2.2.0 -> 2.3.0)
#   major: 大版本号 (2.2.0 -> 3.0.0)
#   current: 使用当前版本，不更新
# =================================================================
set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Docker Compose 文件
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
COMPOSE_DEV_FILE="${PROJECT_ROOT}/docker-compose.dev.yml"

# 镜像名称
BACKEND_IMAGE="novel_system-backend"
NGINX_IMAGE="novel_system-nginx"

# 仓库名称
REGISTRY="${REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

cd "${PROJECT_ROOT}"

# 显示彩色信息
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 获取当前版本号
get_current_version() {
    grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'
}

# 更新版本号
update_version() {
    local version_type=$1
    local current_version=$(get_current_version)
    IFS='.' read -r major minor patch <<< "$current_version"
    
    case $version_type in
        major)
            new_major=$((major + 1))
            new_minor=0
            new_patch=0
            ;;
        minor)
            new_major=$major
            new_minor=$((minor + 1))
            new_patch=0
            ;;
        patch|*)
            new_major=$major
            new_minor=$minor
            new_patch=$((patch + 1))
            ;;
    esac
    
    NEW_VERSION="${new_major}.${new_minor}.${new_patch}"
    echo "$NEW_VERSION"
}

# 更新 pyproject.toml
update_pyproject() {
    local new_version=$1
    info "更新 pyproject.toml 版本: $(get_current_version) -> $new_version"
    sed -i.bak "s/^version = \".*\"/version = \"${new_version}\"/" pyproject.toml
    rm -f pyproject.toml.bak
}

# 更新 CHANGELOG.md
update_changelog() {
    local new_version=$1
    local today=$(date +%Y-%m-%d)
    local changelog_file="CHANGELOG.md"
    
    # 检查是否已存在该版本
    if grep -q "## \[${new_version}\]" "$changelog_file" 2>/dev/null; then
        warn "CHANGELOG.md 中已存在版本 ${new_version}"
        return 0
    fi
    
    info "更新 CHANGELOG.md"
    
    # 读取现有内容
    local content=$(cat "$changelog_file")
    
    # 生成新版本条目
    local new_entry="## [${new_version}] - ${today}

### Added
- **版本构建**: 自动版本构建

### Changed
- **镜像更新**: Docker 镜像更新

"
    
    # 在第一个 ## 标题后插入
    if [[ "$content" =~ ^\#\#\#\ \[ ]]; then
        # 找到第一个 ### 行的位置
        local first_line=$(grep -n "^## " "$changelog_file" | head -1 | cut -d: -f1)
        local head_count=$((first_line - 1))
        local tail_start=$first_line
        
        local head="${content:0:$head_count}"
        local tail="${content:$tail_start-1}"
        
        echo "${head}${new_entry}
${tail}" > "$changelog_file"
    else
        # 没有找到，插到开头
        echo -e "${new_entry}\n${content}" > "$changelog_file"
    fi
}

# 构建 Docker 镜像
build_images() {
    local version=$1
    local tag_suffix="${2:-}"
    
    info "开始构建 Docker 镜像..."
    
    # 构建后端镜像
    info "构建后端镜像: ${BACKEND_IMAGE}:${version}${tag_suffix}"
    docker build -t "${BACKEND_IMAGE}:${version}${tag_suffix}" \
                 -t "${BACKEND_IMAGE}:${IMAGE_TAG}${tag_suffix}" \
                 -f backend/Dockerfile .
    
    # 构建 Nginx 镜像
    info "构建 Nginx 镜像: ${NGINX_IMAGE}:${version}${tag_suffix}"
    docker build -t "${NGINX_IMAGE}:${version}${tag_suffix}" \
                 -t "${NGINX_IMAGE}:${IMAGE_TAG}${tag_suffix}" \
                 -f frontend/Dockerfile .
    
    success "镜像构建完成!"
}

# 打 Docker tag 并推送到远程
tag_and_push_images() {
    local version=$1
    local tag_suffix="${2:-}"
    
    if [ -z "$REGISTRY" ]; then
        warn "未设置 REGISTRY，跳过推送镜像"
        return 0
    fi
    
    info "推送镜像到 ${REGISTRY}..."
    
    # Tag 镜像
    docker tag "${BACKEND_IMAGE}:${version}${tag_suffix}" "${REGISTRY}/${BACKEND_IMAGE}:${version}${tag_suffix}"
    docker tag "${BACKEND_IMAGE}:${version}${tag_suffix}" "${REGISTRY}/${BACKEND_IMAGE}:${IMAGE_TAG}${tag_suffix}"
    docker tag "${NGINX_IMAGE}:${version}${tag_suffix}" "${REGISTRY}/${NGINX_IMAGE}:${version}${tag_suffix}"
    docker tag "${NGINX_IMAGE}:${version}${tag_suffix}" "${REGISTRY}/${NGINX_IMAGE}:${IMAGE_TAG}${tag_suffix}"
    
    # 推送镜像
    docker push "${REGISTRY}/${BACKEND_IMAGE}:${version}${tag_suffix}"
    docker push "${REGISTRY}/${BACKEND_IMAGE}:${IMAGE_TAG}${tag_suffix}"
    docker push "${REGISTRY}/${NGINX_IMAGE}:${version}${tag_suffix}"
    docker push "${REGISTRY}/${NGINX_IMAGE}:${IMAGE_TAG}${tag_suffix}"
    
    success "镜像推送完成!"
}

# Git 提交和打 tag
git_commit_and_tag() {
    local version=$1
    local do_commit=$2
    
    if [ "$do_commit" != "true" ]; then
        info "跳过 Git 提交"
        return 0
    fi
    
    info "Git 提交和打 tag..."
    
    # 检查是否有更改
    if git diff --quiet && git diff --staged --quiet; then
        warn "没有需要提交的更改"
        return 0
    fi
    
    # 添加更改
    git add pyproject.toml CHANGELOG.md
    
    # 提交
    git commit -m "release: prepare v${version} release"
    
    # 创建 tag
    git tag -a "v${version}" -m "Release version ${version}"
    
    success "Git 提交和 tag 完成!"
    
    echo ""
    info "请手动推送:"
    echo "  git push origin <branch>"
    echo "  git push origin v${version}"
}

# 显示帮助
show_help() {
    cat << EOF
用法: $(basename "$0") [选项]

自动构建 Docker 镜像并更新版本号

选项:
  patch        小版本号升级 (2.2.0 -> 2.2.1) [默认]
  minor        中版本号升级 (2.2.0 -> 2.3.0)
  major        大版本号升级 (2.2.0 -> 3.0.0)
  current      使用当前版本，不更新

环境变量:
  REGISTRY     Docker 镜像仓库地址 (如: docker.io/username)
  IMAGE_TAG    镜像标签 (默认: latest)

示例:
  $(basename "$0")              # patch 版本升级并构建
  $(basename "$0") minor        # minor 版本升级并构建
  $(basename "$0") current      # 使用当前版本构建
  REGISTRY=docker.io/user $(basename "$0")  # 构建并推送到远程
EOF
}

# 主函数
main() {
    local version_type="${1:-patch}"
    local update_version_flag="true"
    
    # 解析参数
    case "$version_type" in
        -h|--help)
            show_help
            exit 0
            ;;
        patch|minor|major|current)
            ;;
        *)
            error "未知参数: $version_type"
            ;;
    esac
    
    if [ "$version_type" == "current" ]; then
        update_version_flag="false"
        version_type="patch"
    fi
    
    # 获取当前版本
    local current_version=$(get_current_version)
    info "当前版本: ${current_version}"
    
    # 确定新版本
    if [ "$update_version_flag" == "true" ]; then
        NEW_VERSION=$(update_version "$version_type")
        info "新版本: ${NEW_VERSION}"
    else
        NEW_VERSION="$current_version"
        info "使用当前版本: ${NEW_VERSION}"
    fi
    
    echo ""
    
    # 确认操作
    if [ "$update_version_flag" == "true" ]; then
        read -p "确认更新版本 (y/n)? " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "取消操作"
            exit 0
        fi
    fi
    
    echo ""
    
    # 更新版本文件
    if [ "$update_version_flag" == "true" ]; then
        update_pyproject "$NEW_VERSION"
        update_changelog "$NEW_VERSION"
    fi
    
    # 构建镜像
    build_images "$NEW_VERSION" ""
    
    # 推送到远程仓库（如果有设置）
    tag_and_push_images "$NEW_VERSION" ""
    
    # Git 提交
    echo ""
    read -p "是否提交到 Git (y/n)? " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git_commit_and_tag "$NEW_VERSION" "true"
    fi
    
    echo ""
    success "构建完成!"
    echo ""
    info "镜像版本:"
    echo "  ${BACKEND_IMAGE}:${NEW_VERSION}"
    echo "  ${NGINX_IMAGE}:${NEW_VERSION}"
    echo ""
    info "如需部署到生产环境:"
    echo "  docker-compose -f docker-compose.prod.yml up -d"
}

# 运行主函数
main "$@"
