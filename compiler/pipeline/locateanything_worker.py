# Copyright (c) 2026, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

"""LocateAnything model adapter used by calibration preparation."""

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor, AutoTokenizer


class LocateAnythingWorker:
    """Load LocateAnything once and run calibration reference inference."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        dtype: torch.dtype = torch.bfloat16,
    ) -> None:
        """Initialize the model, processor, and tokenizer.

        Args:
            model_path: Local LocateAnything checkpoint directory.
            device: PyTorch device used for reference inference.
            dtype: Floating-point dtype used by the model and image tensors.
        """
        self.device = device
        self.dtype = dtype
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
        )
        self.processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=True,
        )
        self.model = AutoModel.from_pretrained(
            model_path,
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(device).eval()

    @torch.no_grad()
    def predict(
        self,
        image: Image.Image,
        question: str,
        generation_mode: str = "hybrid",
        max_new_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 0,
        repetition_penalty: float = 1.1,
        verbose: bool = True,
    ) -> dict:
        """Run one image-prompt query through the Float reference model.

        Args:
            image: RGB image passed to LocateAnything.
            question: LocateAnything task prompt.
            generation_mode: Model generation mode, such as hybrid or slow.
            max_new_tokens: Maximum number of generated tokens.
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability.
            top_k: Top-k cutoff; zero disables top-k filtering.
            repetition_penalty: Repetition penalty applied during generation.
            verbose: Whether the model returns timing statistics.

        Returns:
            A dictionary containing the generated answer and optional runtime
            history and statistics.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": question},
                ],
            }
        ]
        text = self.processor.py_apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        images, videos = self.processor.process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=images,
            videos=videos,
            return_tensors="pt",
        ).to(self.device)

        response = self.model.generate(
            pixel_values=inputs["pixel_values"].to(self.dtype),
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            image_grid_hws=inputs.get("image_grid_hws"),
            tokenizer=self.tokenizer,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            generation_mode=generation_mode,
            temperature=temperature,
            do_sample=True,
            top_p=top_p,
            top_k=None if top_k <= 0 else top_k,
            repetition_penalty=repetition_penalty,
            verbose=verbose,
        )

        answer = response[0] if isinstance(response, tuple) else response
        result = {"answer": answer}
        if isinstance(response, tuple) and len(response) >= 3:
            result["history"] = response[1]
            result["stats"] = response[2]
        return result
