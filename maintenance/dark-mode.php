<?php

// The iPad shows every screen through the mirror page's "Dark" display mode,
// which inverts the whole picture. These per-plugin CSS patches (kept in
// config/dark-mode.json) pre-correct the parts that would otherwise come out
// wrong: screens that are already dark, photos, flags and QR codes.
// Safe to run repeatedly; run by `make dark-mode` and `make config-restore`.

use App\Actions\RenderPluginImage;
use App\Models\Device;
use App\Models\Plugin;

$patches = json_decode(file_get_contents('/tmp/dark-mode.json'), true);
$device = Device::first();

foreach ($patches as $name => $css) {
    $plugin = Plugin::where('name', $name)->first();
    if (! $plugin) {
        echo "SKIPPED {$name} (not installed)\n";

        continue;
    }

    $block = "<!-- dark-mode:start --><style>{$css}</style><!-- dark-mode:end -->";
    $markup = preg_replace('/\n?<!-- dark-mode:start -->.*?<!-- dark-mode:end -->/s', '', $plugin->render_markup);
    $markup = rtrim($markup)."\n".$block;

    if ($markup === $plugin->render_markup) {
        continue;
    }

    $plugin = Plugin::find($plugin->id);
    $plugin->render_markup = $markup;
    $plugin->save();
    if ($device) {
        app(RenderPluginImage::class)->handle($plugin, $device, true);
    }
    echo "PATCHED {$name}\n";
}
