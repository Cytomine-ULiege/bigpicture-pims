# * Copyright (c) 2020. Authors: see NOTICE file.
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *      http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.

from fastapi import APIRouter, Depends

from pims.api.exceptions import check_representation_existence
from pims.api.utils.annotation_parameter import parse_annotations, get_annotation_region
from pims.api.utils.header import add_image_size_limit_header, ImageAnnotationRequestHeaders
from pims.api.utils.image_parameter import check_zoom_validity, check_level_validity, get_window_output_dimensions, \
    safeguard_output_dimensions, ensure_list
from pims.api.utils.mimetype import get_output_format, VISUALISATION_MIMETYPES, OutputExtension, \
    extension_path_parameter
from pims.api.utils.models import AnnotationStyleMode, AnnotationMaskRequest, AnnotationCropRequest, Colorspace, \
    AnnotationDrawingRequest
from pims.api.utils.parameter import imagepath_parameter
from pims.api.window import _show_window
from pims.config import Settings, get_settings
from pims.files.file import Path
from pims.processing.annotations import annotation_crop_affine_matrix
from pims.processing.color import WHITE
from pims.processing.image_response import MaskResponse

router = APIRouter()
api_tags = ['Annotations']


@router.post('/image/{filepath:path}/annotation/mask{extension:path}', tags=api_tags)
def show_mask(
        body: AnnotationMaskRequest,
        path: Path = Depends(imagepath_parameter),
        extension: OutputExtension = Depends(extension_path_parameter),
        headers: ImageAnnotationRequestHeaders = Depends(),
        config: Settings = Depends(get_settings)
):
    """
    **`GET with body` - when a GET with URL encoded query parameters is not possible due to URL size limits, a POST
    with body content must be used.**

    The mask is a generated image where geometries are filled by their respective `fill_color`. The background is
    black.

    The input spatial region is given by the rectangular envelope of all geometries multiplied by an optional
    context factor. The target size is given by one of the scaling factors (`size`, `width`, `height`, `zoom` or
    `level`).

    By default, a binary mask with white foreground is returned as the default fill color is white for every
    annotation.

    Annotation `stroke_width` and `stroke_color` are ignored.
    """
    return _show_mask(path, **body.dict(), extension=extension, headers=headers, config=config)


def _show_mask(
        path: Path,
        annotations,
        context_factor,
        height, width, length, zoom, level,
        extension, headers, config
):
    in_image = path.get_spatial()
    check_representation_existence(in_image)

    annots = parse_annotations(
        ensure_list(annotations),
        ignore_fields=['stroke_width', 'stroke_color'],
        default={'fill_color': WHITE},
        origin=headers.annot_origin, im_height=in_image.height
    )

    region = get_annotation_region(in_image, annots, context_factor)

    out_format, mimetype = get_output_format(extension, headers.accept, VISUALISATION_MIMETYPES)
    check_zoom_validity(in_image.pyramid, zoom)
    check_level_validity(in_image.pyramid, level)
    req_size = get_window_output_dimensions(in_image, region, height, width, length, zoom, level)
    out_size = safeguard_output_dimensions(headers.safe_mode, config.output_size_limit, *req_size)
    out_width, out_height = out_size

    affine = annotation_crop_affine_matrix(annots.region, region, out_width, out_height)

    return MaskResponse(
        in_image, annots, affine,
        out_width, out_height, 8, out_format
    ).http_response(
        mimetype,
        extra_headers=add_image_size_limit_header(dict(), *req_size, *out_size)
    )


@router.post('/image/{filepath:path}/annotation/crop{extension:path}', tags=api_tags)
def show_crop(
        body: AnnotationCropRequest,
        path: Path = Depends(imagepath_parameter),
        extension: OutputExtension = Depends(extension_path_parameter),
        headers: ImageAnnotationRequestHeaders = Depends(),
        config: Settings = Depends(get_settings)
):
    """
    **`GET with body` - when a GET with URL encoded query parameters is not possible due to URL size limits, a POST
    with body content must be used.**

    The crop is similar to an image window but where the transparency of the background can be adjusted.

    The input spatial region is given by the rectangular envelope of all geometries multiplied by an optional
    context factor. The target size is given by one of the scaling factors (`size`, `width`, `height`, `zoom` or
    `level`).

    By default, the background transparency is set to 100 which is also known as *alpha mask*. When the
    background transparency is set to 0, foreground and background cannot be distinguished.

    Annotation `fill_color`, `stroke_width` and `stroke_color` are ignored.
    """
    return _show_crop(path, **body.dict(), extension=extension, headers=headers, config=config)


def _show_crop(
        path: Path,
        annotations,
        context_factor,
        background_transparency,
        height, width, length, zoom, level,
        channels, z_slices, timepoints,
        min_intensities, max_intensities, filters, gammas,
        bits, colorspace,
        extension, headers, config,
        colormaps=None, c_reduction="ADD", z_reduction=None, t_reduction=None,
):
    in_image = path.get_spatial()
    check_representation_existence(in_image)

    annots = parse_annotations(
        ensure_list(annotations),
        ignore_fields=['stroke_width', 'stroke_color'],
        default={'fill_color': WHITE},
        origin=headers.annot_origin, im_height=in_image.height
    )

    region = get_annotation_region(in_image, annots, context_factor)

    annot_style = dict(
        mode=AnnotationStyleMode.CROP,
        background_transparency=background_transparency
    )

    return _show_window(
        path, region,
        height, width, length, zoom, level,
        channels, z_slices, timepoints,
        min_intensities, max_intensities,
        filters, gammas, bits, colorspace,
        annots, annot_style,
        extension, headers, config,
        colormaps, c_reduction, z_reduction, t_reduction
    )


@router.post('/image/{filepath:path}/annotation/drawing{extension:path}', tags=api_tags)
def show_drawing(
        body: AnnotationDrawingRequest,
        path: Path = Depends(imagepath_parameter),
        extension: OutputExtension = Depends(extension_path_parameter),
        headers: ImageAnnotationRequestHeaders = Depends(),
        config: Settings = Depends(get_settings)
):
    """
    **`GET with body` - when a GET with URL encoded query parameters is not possible due to URL size limits, a POST
    with body content must be used.**

    Get an annotation crop (with apparent background) where annotations are drawn according to their respective
    `fill_color`, `stroke_width` and `stroke_color`.

    The input spatial region is given by the rectangular envelope of all geometries multiplied by an optional
    context factor. The target size is given by one of the scaling factors (`size`, `width`, `height`, `zoom` or
    `level`).
    """
    return _show_drawing(path, **body.dict(), extension=extension, headers=headers, config=config)


def _show_drawing(
        path: Path,
        annotations,
        context_factor,
        try_square, point_cross, point_envelope_length,
        height, width, length, zoom, level,
        channels, z_slices, timepoints,
        min_intensities, max_intensities, filters, gammas, log,
        extension, headers, config,
        colormaps=None, c_reduction="ADD", z_reduction=None, t_reduction=None,
):
    in_image = path.get_spatial()
    check_representation_existence(in_image)

    annots = parse_annotations(
        ensure_list(annotations),
        ignore_fields=['fill_color'],
        default={'stroke_width': 1},
        point_envelope_length=point_envelope_length,
        origin=headers.annot_origin, im_height=in_image.height
    )

    region = get_annotation_region(in_image, annots, context_factor, try_square)

    annot_style = dict(
        mode=AnnotationStyleMode.DRAWING,
        point_cross=point_cross,
        point_envelope_length=point_envelope_length
    )

    return _show_window(
        path, region,
        height, width, length, zoom, level,
        channels, z_slices, timepoints,
        min_intensities, max_intensities,
        filters, gammas, 8, Colorspace.AUTO,
        annots, annot_style,
        extension, headers, config,
        colormaps, c_reduction, z_reduction, t_reduction
    )


def show_spectra(filepath, body):
    pass


def show_footprint(filepath, body):
    pass
