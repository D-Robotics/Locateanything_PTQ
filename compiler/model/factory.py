"""Model registry for LocateAnything Vision and Language compilation."""

_model_builders = {}


def register_model(name, marches=None):
    """
    Function:
        Register a model builder for the supported compiler marches.

    Args:
        name: Public model name.
        marches: Supported target architectures.

    Returns:
        A decorator that records the builder function.
    """
    def decorator(func):
        """
        Function:
            Store one model builder in the registry.

        Args:
            func: Builder callable.

        Returns:
            The unchanged builder callable.
        """
        _model_builders[name] = {"builder": func, "marches": marches or []}
        return func

    return decorator


def get_supported_models():
    """
    Function:
        Return registered model names.

    Args:
        None.

    Returns:
        List of public model names.
    """
    return list(_model_builders)


def get_marches_with_model(model_name: str) -> list[str]:
    """
    Function:
        Return target marches registered for one model.

    Args:
        model_name: Public model name.

    Returns:
        Supported march names, or an empty list.
    """
    return _model_builders.get(model_name, {}).get("marches", [])


def get_supported_marches():
    """
    Function:
        Return all target marches supported by the registry.

    Args:
        None.

    Returns:
        Sorted list of march names.
    """
    return sorted(
        {
            march
            for model_info in _model_builders.values()
            for march in model_info["marches"]
        }
    )

def create_model_api(model_name, args):
    """
    Function:
        Create the selected model compiler API from parsed arguments.

    Args:
        model_name: Registered model name.
        args: Compiler argument namespace.

    Returns:
        Model API instance, or ``None`` for an unsupported selection.
    """
    model_info = _model_builders.get(model_name)
    if model_info is None:
        print(f"Model '{model_name}' is not supported.")
        return None

    if args.march not in model_info["marches"]:
        supported = ", ".join(model_info["marches"])
        print(f"March {args.march} is not supported for {model_name}: {supported}")
        return None

    return model_info["builder"](args)


def _primary_device(args):
    """
    Function:
        Select the first device from a parsed device argument.

    Args:
        args: Compiler argument namespace.

    Returns:
        One device string.
    """
    return args.device[0] if isinstance(args.device, list) else args.device


@register_model("locateanything-lm-3b", ["nash-p"])
def _build_locateanything_lm_3b(args):
    """
    Function:
        Construct the LocateAnything Language compiler API.

    Args:
        args: Parsed Language compiler arguments.

    Returns:
        Configured LocateAnythingLanguageApi instance.
    """
    from model.language import LocateAnythingLanguageApi

    return LocateAnythingLanguageApi(
        input_model_path=args.input_model_path,
        output_model_path=args.output_model_path,
        chunk_size=args.chunk_size,
        batch_size=args.batch_size,
        cache_len=args.cache_len,
        decode_seq_len=args.decode_seq_len,
        device=_primary_device(args),
        w_bits=args.w_bits,
        lm_head_w_bits=args.lm_head_w_bits,
        prefill_core_num=args.prefill_core_num,
        decode_core_num=args.decode_core_num,
        ar_core_num=args.ar_core_num,
        march=args.march,
        hidden_rotation_path=args.hidden_rotation_path,
        apply_hidden_rotation=not args.disable_hidden_rotation,
        export_only=args.export_only,
        calibration_scale_manifest=args.calibration_scale_manifest,
        compact_logits=args.compact_logits,
        fuse_initial_pbd=args.fuse_initial_pbd,
    )


@register_model("locateanything-vit-3b", ["nash-p"])
def _build_locateanything_vit_3b(args):
    """
    Function:
        Construct the LocateAnything Vision compiler API.

    Args:
        args: Parsed Vision compiler arguments.

    Returns:
        Configured LocateAnythingVisionApi instance.
    """
    from model.vision import LocateAnythingVisionApi

    return LocateAnythingVisionApi(
        input_model_path=args.input_model_path,
        output_model_path=args.output_model_path,
        image_width=args.image_width,
        image_height=args.image_height,
        resize_mode=args.resize_mode,
        letterbox_fill=args.letterbox_fill,
        device=_primary_device(args),
        w_bits=args.w_bits,
        vit_core_num=args.vit_core_num,
        march=args.march,
        hidden_rotation_path=args.hidden_rotation_path,
        apply_hidden_rotation=not args.disable_hidden_rotation,
        export_only=args.export_only,
        calibration_scale_manifest=args.calibration_scale_manifest,
    )
