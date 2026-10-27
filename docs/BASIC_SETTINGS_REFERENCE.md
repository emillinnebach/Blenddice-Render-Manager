# Basic Settings Reference

Every option listed here is already in `basic_settings.json`. `null` = not applied; set a value to apply it.
Keys are Blender property names. Enum values and `true`/`false` are case-sensitive.

Not covered on purpose: frame range / time stretching, color management (handled by your OCIO setup), viewport-only settings and Eevee. Any other property can still be added by hand to the matching section (`render`, `image_settings`, `cycles`, `eevee`, `scene`).


## Output > Format

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Resolution X | `render` | `resolution_x` | pixels |
| Resolution Y | `render` | `resolution_y` | pixels |
| Resolution % | `render` | `resolution_percentage` | 1-32767 |
| Pixel Aspect X | `render` | `pixel_aspect_x` | 1.0-200.0 |
| Pixel Aspect Y | `render` | `pixel_aspect_y` | 1.0-200.0 |
| Render Region | `render` | `use_border` | true/false |
| Crop to Render Region | `render` | `use_crop_to_border` | true/false |
| Frame Rate (fps) | `render` | `fps` | whole number, e.g. 25 |
| Frame Rate base | `render` | `fps_base` | 1.0, or 1.001 for 23.976 / 29.97 |

## Output > Stereoscopy

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Stereoscopy (panel checkbox) | `render` | `use_multiview` | true/false |
| Stereoscopy: Stereo 3D / Multi-View | `render` | `views_format` | STEREO_3D | MULTIVIEW |

## Output > Output

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Output Path | `render` | `filepath` | forward slashes; // = relative to the .blend |
| File Extensions | `render` | `use_file_extension` | true/false |
| Overwrite | `render` | `use_overwrite` | true/false |
| Placeholders | `render` | `use_placeholder` | true/false |
| Cache Result | `render` | `use_render_cache` | true/false |
| Output checkbox (write frames to disk) | `render` | `save_output` | true/false - Blender 5.2+ only, skipped with a warning on older versions |

## Output > Image format

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Media Type | `image_settings` | `media_type` | IMAGE (see Blender's dropdown for the others) |
| File Format | `image_settings` | `file_format` | PNG | JPEG | TIFF | OPEN_EXR | OPEN_EXR_MULTILAYER | ... |
| Color | `image_settings` | `color_mode` | BW | RGB | RGBA |
| Color Depth | `image_settings` | `color_depth` | text: "8" | "10" | "12" | "16" | "32" (which ones exist depends on the file format) |
| Compression (PNG) | `image_settings` | `compression` | 0-100 |
| Quality (JPEG, WebP, ...) | `image_settings` | `quality` | 0-100 |
| Codec (EXR) | `image_settings` | `exr_codec` | NONE | ZIP | ZIPS | PIZ | RLE | PXR24 | B44 | B44A | DWAA | DWAB |
| Preview (EXR) | `image_settings` | `use_preview` | true/false |
| Interleave (EXR) | `image_settings` | `use_exr_interleave` | true/false |
| Compression (TIFF) | `image_settings` | `tiff_codec` | NONE | DEFLATE | LZW | PACKBITS |
| Views > View Format | `image_settings` | `views_format` | INDIVIDUAL | STEREO_3D |

## Output > Metadata

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Burn Into Image | `render` | `use_stamp` | true/false |

## Output > Post Processing

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Compositing | `render` | `use_compositing` | true/false - keep on when save_output is off, otherwise nothing is written |
| Sequencer | `render` | `use_sequencer` | true/false |
| Dither | `render` | `dither_intensity` | 0.0-2.0 |

## Render > Engine

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Render Engine | `render` | `engine` | CYCLES | BLENDER_EEVEE | BLENDER_WORKBENCH |

## Render > Film

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Transparent | `render` | `film_transparent` | true/false |

## Render > Motion Blur

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Motion Blur | `render` | `use_motion_blur` | true/false |
| Position | `render` | `motion_blur_position` | START | CENTER | END |
| Shutter | `render` | `motion_blur_shutter` | frames, e.g. 0.5 |

## Render > Performance

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Persistent Data | `render` | `use_persistent_data` | true/false |
| Threads Mode | `render` | `threads_mode` | AUTO | FIXED |
| Threads (Fixed) | `render` | `threads` | 1-1024 |

## Render > Simplify

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Simplify (checkbox) | `render` | `use_simplify` | true/false |
| Max Subdivision (Render) | `render` | `simplify_subdivision_render` | 0-6 |
| Max Child Particles (Render) | `render` | `simplify_child_particles_render` | 0.0-1.0 |
| Volume Resolution | `render` | `simplify_volumes` | 0.0-1.0 |

## Render > Device

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Device | `cycles` | `device` | CPU | GPU |

## Render > Sampling

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Max Samples | `cycles` | `samples` | 0 = unlimited (noise threshold decides) |
| Noise Threshold (checkbox) | `cycles` | `use_adaptive_sampling` | true/false |
| Noise Threshold | `cycles` | `adaptive_threshold` | 0.0-1.0, e.g. 0.01 |
| Min Samples | `cycles` | `adaptive_min_samples` | whole number |
| Time Limit | `cycles` | `time_limit` | seconds, 0 = off |

## Render > Denoise

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Denoise | `cycles` | `use_denoising` | true/false |
| Denoiser | `cycles` | `denoiser` | OPENIMAGEDENOISE | OPTIX |
| Passes | `cycles` | `denoising_input_passes` | RGB | RGB_ALBEDO | RGB_ALBEDO_NORMAL |
| Prefilter | `cycles` | `denoising_prefilter` | NONE | FAST | ACCURATE |
| Quality | `cycles` | `denoising_quality` | HIGH | BALANCED | FAST |
| Use GPU | `cycles` | `denoising_use_gpu` | true/false |

## Render > Sampling > Advanced

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Seed | `cycles` | `seed` | whole number |
| Use Animated Seed | `cycles` | `use_animated_seed` | true/false |
| Pattern | `cycles` | `sampling_pattern` | AUTOMATIC | SOBOL_BURLEY | TABULATED_SOBOL | BLUE_NOISE | BLUE_NOISE_FIRST | BLUE_NOISE_ROUND |
| Scrambling Distance | `cycles` | `scrambling_distance` | 0.0-1.0 |
| Automatic Scrambling Distance | `cycles` | `auto_scrambling_distance` | true/false |
| Sample Offset | `cycles` | `sample_offset` | whole number |
| Sample Subset (checkbox) | `cycles` | `use_sample_subset` | true/false |
| Sample Subset Length | `cycles` | `sample_subset_length` | whole number |
| Light Tree | `cycles` | `use_light_tree` | true/false |
| Light Threshold | `cycles` | `light_sampling_threshold` | 0.0-1.0 |

## Render > Sampling > Path Guiding (CPU)

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Path Guiding | `cycles` | `use_guiding` | true/false |
| Surface Guiding | `cycles` | `use_surface_guiding` | true/false |
| Volume Guiding | `cycles` | `use_volume_guiding` | true/false |
| Training Samples | `cycles` | `guiding_training_samples` | whole number |

## Render > Light Paths

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Max Bounces: Total | `cycles` | `max_bounces` | whole number |
| Max Bounces: Diffuse | `cycles` | `diffuse_bounces` | whole number |
| Max Bounces: Glossy | `cycles` | `glossy_bounces` | whole number |
| Max Bounces: Transmission | `cycles` | `transmission_bounces` | whole number |
| Max Bounces: Volume | `cycles` | `volume_bounces` | whole number |
| Max Bounces: Transparent | `cycles` | `transparent_max_bounces` | whole number |
| Min Light Bounces | `cycles` | `min_light_bounces` | whole number |
| Min Transparent Bounces | `cycles` | `min_transparent_bounces` | whole number |
| Clamping: Direct Light | `cycles` | `sample_clamp_direct` | 0.0 = off |
| Clamping: Indirect Light | `cycles` | `sample_clamp_indirect` | 0.0 = off |
| Caustics: Reflective | `cycles` | `caustics_reflective` | true/false |
| Caustics: Refractive | `cycles` | `caustics_refractive` | true/false |
| Caustics: Filter Glossy | `cycles` | `blur_glossy` | 0.0-10.0 |

## Render > Fast GI Approximation

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Fast GI (checkbox) | `cycles` | `use_fast_gi` | true/false |
| Method | `cycles` | `fast_gi_method` | REPLACE | ADD |
| Render Bounces | `cycles` | `ao_bounces_render` | whole number |

## Render > Volumes

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Step Rate (Render) | `cycles` | `volume_step_rate` | 0.01-100.0 |
| Max Steps | `cycles` | `volume_max_steps` | whole number |

## Render > Simplify > Culling

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Texture Limit (Render) | `cycles` | `texture_limit_render` | text, e.g. "OFF" | "128" | "256" | "512" | "1024" | "2048" | "4096" | "8192" |
| Camera Culling | `cycles` | `use_camera_cull` | true/false |
| Camera Cull Margin | `cycles` | `camera_cull_margin` | 0.0-5.0 |
| Distance Culling | `cycles` | `use_distance_cull` | true/false |
| Distance Cull Margin | `cycles` | `distance_cull_margin` | 0.0-5000.0 |

## Render > Motion Blur

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Rolling Shutter | `cycles` | `rolling_shutter_type` | NONE | TOP |
| Rolling Shutter Duration | `cycles` | `rolling_shutter_duration` | 0.0-1.0 |

## Render > Film

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Exposure | `cycles` | `film_exposure` | 0.0-10.0 |
| Pixel Filter | `cycles` | `pixel_filter_type` | BOX | GAUSSIAN | BLACKMAN_HARRIS |
| Filter Width | `cycles` | `filter_width` | pixels, e.g. 1.5 |
| Transparent: Transparent Glass | `cycles` | `film_transparent_glass` | true/false |
| Transparent: Roughness Threshold | `cycles` | `film_transparent_roughness` | 0.0-1.0 |

## Render > Performance

| Blender UI | Section | Key | Values |
|---|---|---|---|
| Tile Size | `cycles` | `tile_size` | whole number, e.g. 2048 |

## Special sections

| Section | Key | Values |
|---|---|---|
| `world` | `surface_color` | `"#RRGGBB"`, `"#RRGGBBAA"` (sRGB hex) or a list of 3-4 linear floats - sets the World background color |
| `outliner` | `show_restrict_column_holdout` | true/false - shows the Holdout column in every Outliner |
| `outliner` | `show_restrict_column_indirect_only` | true/false - shows the Indirect Only column in every Outliner |
