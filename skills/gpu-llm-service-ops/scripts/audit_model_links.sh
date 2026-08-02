#!/usr/bin/env bash
set -euo pipefail

LOCAL_MODELS="${1:-/home/jovyan/code/src/ComfyUI/models}"
JUSCENT_MODELS="${2:-/home/share/game/juscent/models}"
SEASUN_MODELS="${3:-/home/share/game/seasun/models}"

echo "--- paths ---"
echo "LOCAL_MODELS=${LOCAL_MODELS}"
echo "JUSCENT_MODELS=${JUSCENT_MODELS}"
echo "SEASUN_MODELS=${SEASUN_MODELS}"

count_find() {
  { find "$@" 2>/dev/null || true; } | wc -l | tr -d ' '
}

print_path_stat() {
  local path="$1"
  if [ -e "${path}" ] || [ -L "${path}" ]; then
    stat -c '%F %A %U %G %n' "${path}" 2>/dev/null || true
  else
    echo "missing ${path}"
  fi
}

summarize_local_model_dir() {
  local name="$1"
  local path="${LOCAL_MODELS}/${name}"
  [ -e "${path}" ] || [ -L "${path}" ] || {
    printf '%-18s missing %s\n' "${name}" "${path}"
    return
  }

  local total links broken files
  total="$(count_find "${path}" -mindepth 1 -maxdepth 2)"
  links="$(count_find "${path}" -mindepth 1 -maxdepth 2 -type l)"
  broken="$(count_find "${path}" -mindepth 1 -maxdepth 2 -xtype l)"
  files="$(count_find "${path}" -mindepth 1 -maxdepth 2 -type f)"

  printf '%-18s total=%s links=%s broken=%s files=%s' "${name}" "${total}" "${links}" "${broken}" "${files}"
  if [ -L "${path}" ]; then
    printf ' top_link->%s' "$(readlink -f "${path}" 2>/dev/null || readlink "${path}")"
  fi
  printf '\n'
}

summarize_share_root() {
  local label="$1"
  local path="$2"
  echo "--- ${label} share root ---"
  print_path_stat "${path}"
  [ -d "${path}" ] || return
  printf 'root_dirs=%s\n' "$(count_find "${path}" -maxdepth 1 -type d)"
  printf 'root_symlinks=%s\n' "$(count_find "${path}" -maxdepth 1 -type l)"
  printf 'broken_symlinks=%s\n' "$(count_find "${path}" -xtype l)"
  find "${path}" -maxdepth 1 -type d -printf '  %f\n' 2>/dev/null | sort | head -60 || true
}

echo "--- counts ---"
printf 'local_symlinks=%s\n' "$(count_find "${LOCAL_MODELS}" -type l)"
printf 'local_broken_symlinks=%s\n' "$(count_find "${LOCAL_MODELS}" -xtype l)"

echo "--- important local model dirs ---"
for name in checkpoints loras diffusion_models text_encoders clip vae embeddings unet; do
  summarize_local_model_dir "${name}"
done

echo "--- local top-level ---"
find "${LOCAL_MODELS}" -maxdepth 1 -mindepth 1 -printf '%y %p -> %l\n' 2>/dev/null | sort || true

echo "--- local symlinks ---"
find "${LOCAL_MODELS}" -type l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- broken local symlinks ---"
find "${LOCAL_MODELS}" -xtype l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- large real local files >100M ---"
find "${LOCAL_MODELS}" -xdev -type f ! -xtype l -size +100M -printf '%s %p\n' 2>/dev/null | sort -nr | head -100 || true

summarize_share_root "juscent" "${JUSCENT_MODELS}"
summarize_share_root "seasun" "${SEASUN_MODELS}"

echo "--- important shared targets ---"
for path in \
  "${JUSCENT_MODELS}/loras" \
  "${JUSCENT_MODELS}/text_encoders" \
  "${JUSCENT_MODELS}/diffusion_models" \
  "${JUSCENT_MODELS}/checkpoints" \
  "${JUSCENT_MODELS}/huggingface/hub" \
  "${JUSCENT_MODELS}/.hf_cache/hub" \
  "${SEASUN_MODELS}/.hf_cache/hub" \
  "${SEASUN_MODELS}/.modelscope"; do
  print_path_stat "${path}"
done

echo "--- juscent shared root symlink aliases ---"
find "${JUSCENT_MODELS}" -maxdepth 1 -type l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- seasun shared root symlink aliases ---"
find "${SEASUN_MODELS}" -maxdepth 1 -type l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- broken juscent shared symlinks ---"
find "${JUSCENT_MODELS}" -xtype l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- broken seasun shared symlinks ---"
find "${SEASUN_MODELS}" -xtype l -printf '%p -> %l\n' 2>/dev/null | sort || true

echo "--- local disk usage ---"
du -sh "${LOCAL_MODELS}" 2>/dev/null || true
