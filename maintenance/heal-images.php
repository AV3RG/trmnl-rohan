<?php
// Re-renders any plugin whose rendered image file has gone missing.
// The server deletes unreferenced images after each render; when two renders overlap, one can
// lose its fresh image, and the device then shows the TRMNL logo until that plugin's data goes
// stale. Run through `make heal` (a systemd timer does this every minute).
use App\Actions\RenderPluginImage;
use App\Models\{Device, Plugin};
use Illuminate\Support\Facades\Storage;

$device = Device::first();
foreach ($device ? Plugin::all() : [] as $plugin) {
    if ($plugin->current_image && Storage::disk('public')->exists("images/generated/{$plugin->current_image}.png")) {
        continue;
    }
    app(RenderPluginImage::class)->handle($plugin, $device, true);
    echo "HEALED {$plugin->name}\n";
}
