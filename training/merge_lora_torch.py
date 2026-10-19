"""
Merge LoRA weights into the base model — official Nebius Token Factory recipe.

Source of truth: https://docs.tokenfactory.nebius.com/post-training/merge-moe-lora-weights
(adapted verbatim; requires: pip install safetensors huggingface_hub transformers peft torch)

For a lighter, torch-free variant that runs on small machines, see
``training/merge_lora_light.py`` (numpy + ml_dtypes; same math, bounded memory).

---

# Instruction

1. Do not forget to install dependencies:
> pip install safetensors huggingface_hub transformers peft

2. Download lora weights from UI or via cli

3. Initial weights must be the same as specified by the lora adapter
    In order to obtain initial weights, you can run:
> hf download unsloth/gpt-oss-20b-BF16 --local-dir gpt-oss-20b-BF16
Now you can specify it via `--orig_ckpt_path gpt-oss-20b-BF16`

4. Run conversion
> python merge_lora_torch.py -i <base-ckpt> -l <lora-ckpt> -o <merged-weights-ckpt>
"""

import argparse
import re
import shutil
from pathlib import Path

import torch
from peft import LoraConfig
from safetensors import safe_open
from safetensors.torch import save_file


ALLOWED_LORA_LAYERS = [
    r"model.layers.*.self_attn",
]


def _compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    compiled = []
    for p in patterns:
        esc = re.escape(p).replace(r"\*", ".*")
        regex = r"^" + esc + r"(?:\..*)?$"
        compiled.append(re.compile(regex))
    return compiled


INCLUDE_PATTERNS = _compile_patterns(ALLOWED_LORA_LAYERS)


def _needs_lora_merge(key: str) -> bool:
    return any(p.match(key) for p in INCLUDE_PATTERNS)


def _merge_lora_weight(
    tensor_name: str,
    tensor: torch.Tensor,
    lora_weights: dict[str, torch.Tensor],
    lora_config: LoraConfig,
) -> torch.Tensor:
    scale = lora_config.lora_alpha / lora_config.r
    tensor_prefix = tensor_name.rsplit(".", 1)[0]  # remove .weight
    A_name, B_name = f"{tensor_prefix}.lora_A.weight", f"{tensor_prefix}.lora_B.weight"
    A, B = (
        lora_weights[A_name],
        lora_weights[B_name],
    )
    deltaW = B @ A
    merged_weight = tensor + scale * deltaW

    del lora_weights[A_name]
    del lora_weights[B_name]
    print(f"Merged layer {tensor_name}")
    return merged_weight


def _process_single_file(
    safetensors_path: Path,
    lora_config: LoraConfig,
    lora_weights: dict[str, torch.Tensor],
    output_ckpt_path: Path,
):
    safetensors = {}
    with safe_open(safetensors_path, framework="torch") as f:
        for tensor_name in f.keys():
            tensor = f.get_tensor(tensor_name)
            if _needs_lora_merge(tensor_name) and tensor_name.endswith(".weight"):
                tensor = _merge_lora_weight(
                    tensor_name,
                    tensor,
                    lora_weights,
                    lora_config,
                )
            safetensors[tensor_name] = tensor

    output_path = output_ckpt_path / safetensors_path.name
    save_file(safetensors, filename=output_path)
    print(f"Merged and unloaded safetensor {output_path}")


def merge_lora_weights(
    orig_ckpt_path: Path | str,
    lora_ckpt_path: Path | str,
    output_ckpt_path: Path | str,
):
    orig_ckpt_path = Path(orig_ckpt_path)
    lora_ckpt_path = Path(lora_ckpt_path)
    output_ckpt_path = Path(output_ckpt_path)
    output_ckpt_path.mkdir(exist_ok=True, parents=True)

    torch.manual_seed(42)
    # torch.cuda.manual_seed(42)  # enable this if CUDA available

    lora_config = LoraConfig.from_pretrained(lora_ckpt_path)
    lora_weights = {}
    with safe_open(
        lora_ckpt_path / "adapter_model.safetensors", framework="torch"
    ) as f:
        for tensor_name in f.keys():
            if not _needs_lora_merge(tensor_name):
                raise ValueError("Provided layer-pattern is not listed as ALLOWED")
            tensor = f.get_tensor(tensor_name)
            lora_weights[tensor_name] = tensor

    safetensor_paths = list(orig_ckpt_path.glob("*.safetensors"))

    for path in safetensor_paths:
        _process_single_file(path, lora_config, lora_weights, output_ckpt_path)

    if len(lora_weights) != 0:
        raise ValueError(f"Found non-merged lora weights: {lora_weights.keys()}")

    for path in set(orig_ckpt_path.glob("*")) - set(
        orig_ckpt_path.glob("*.safetensors")
    ):
        shutil.copy(path, output_ckpt_path / path.name)
    print("Copied the rest of the files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge LoRA weights into main weights")
    parser.add_argument(
        "-i",
        "--orig_ckpt_path",
        type=str,
        required=True,
        help="Path to the original checkpoint directory containing safetensors files",
    )
    parser.add_argument(
        "-l",
        "--lora_ckpt_path",
        type=str,
        required=True,
        help="Path to the output converted checkpoint directory",
    )
    parser.add_argument(
        "-o",
        "--output_ckpt_path",
        type=str,
        required=True,
        help="Path to save merged checkpoint",
    )
    args = parser.parse_args()

    merge_lora_weights(
        orig_ckpt_path=args.orig_ckpt_path,
        lora_ckpt_path=args.lora_ckpt_path,
        output_ckpt_path=args.output_ckpt_path,
    )
