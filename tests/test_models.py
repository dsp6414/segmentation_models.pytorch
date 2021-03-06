import os
import sys
import mock
import pytest
import torch

# mock detection module
sys.modules["torchvision._C"] = mock.Mock()

import segmentation_models_pytorch as smp

IS_TRAVIS = os.environ.get("TRAVIS", False)


def get_encoders():
    travis_exclude_encoders = [
        "senet154",
        "resnext101_32x16d",
        "resnext101_32x32d",
        "resnext101_32x48d",
    ]
    encoders = smp.encoders.get_encoder_names()
    if IS_TRAVIS:
        encoders = [e for e in encoders if e not in travis_exclude_encoders]
    return encoders


ENCODERS = get_encoders()
DEFAULT_ENCODER = "resnet18"
DEFAULT_SAMPLE = torch.ones([1, 3, 64, 64])
DEFAULT_PAN_SAMPLE = torch.ones([2, 3, 256, 256])


def _test_forward(model):
    with torch.no_grad():
        model(DEFAULT_SAMPLE)


def _test_forward_backward(model, sample):
    out = model(sample)
    out.mean().backward()


@pytest.mark.parametrize("encoder_name", ENCODERS)
@pytest.mark.parametrize("encoder_depth", [3, 5])
@pytest.mark.parametrize("model_class", [smp.FPN, smp.PSPNet, smp.Linknet, smp.Unet])
def test_forward(model_class, encoder_name, encoder_depth, **kwargs):
    if model_class is smp.Unet:
        kwargs["decoder_channels"] = (16, 16, 16, 16, 16)[-encoder_depth:]
    model = model_class(
        encoder_name, encoder_depth=encoder_depth, encoder_weights=None, **kwargs
    )
    _test_forward(model)


@pytest.mark.parametrize("model_class", [smp.PAN, smp.FPN, smp.PSPNet, smp.Linknet, smp.Unet])
def test_forward_backward(model_class):
    sample = DEFAULT_PAN_SAMPLE if model_class is smp.PAN else DEFAULT_SAMPLE
    model = model_class(DEFAULT_ENCODER, encoder_weights=None)
    _test_forward_backward(model, sample)


@pytest.mark.parametrize("model_class", [smp.PAN, smp.FPN, smp.PSPNet, smp.Linknet, smp.Unet])
def test_aux_output(model_class):
    model = model_class(
        DEFAULT_ENCODER, encoder_weights=None, aux_params=dict(classes=2)
    )
    sample = DEFAULT_PAN_SAMPLE if model_class is smp.PAN else DEFAULT_SAMPLE
    label_size = (2, 2) if model_class is smp.PAN else (1, 2)
    mask, label = model(sample)
    assert label.size() == label_size


@pytest.mark.parametrize("upsampling", [2, 4, 8])
@pytest.mark.parametrize("model_class", [smp.FPN, smp.PSPNet])
def test_upsample(model_class, upsampling):
    default_upsampling = 4 if model_class is smp.FPN else 8
    model = model_class(DEFAULT_ENCODER, encoder_weights=None, upsampling=upsampling)
    mask = model(DEFAULT_SAMPLE)
    assert mask.size()[-1] / 64 == upsampling / default_upsampling


@pytest.mark.parametrize("model_class", [smp.FPN])
@pytest.mark.parametrize("encoder_name", ENCODERS)
@pytest.mark.parametrize("in_channels", [1, 2, 4])
def test_in_channels(model_class, encoder_name, in_channels):
    sample = torch.ones([1, in_channels, 64, 64])
    model = model_class(DEFAULT_ENCODER, encoder_weights=None, in_channels=in_channels)
    with torch.no_grad():
        model(sample)

    assert model.encoder._in_channels == in_channels


@pytest.mark.parametrize("encoder_name", ENCODERS)
def test_dilation(encoder_name):
    if (encoder_name in ['inceptionresnetv2', 'xception', 'inceptionv4'] or
            encoder_name.startswith('vgg') or encoder_name.startswith('densenet')):
        return

    encoder = smp.encoders.get_encoder(encoder_name)
    encoder.make_dilated(
        stage_list=[5],
        dilation_list=[2],
    )

    encoder.eval()
    with torch.no_grad():
        output = encoder(DEFAULT_SAMPLE)

    shapes = [out.shape[-1] for out in output]
    assert shapes == [64, 32, 16, 8, 4, 4]  # last downsampling replaced with dilation


if __name__ == "__main__":
    pytest.main([__file__])
