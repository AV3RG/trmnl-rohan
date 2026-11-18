<?php
// Uploads plugins/<dir>/template.liquid into the plugin named $PLUGIN_NAME and renders a preview PNG.
// Run through `make plugin-deploy DIR=machine-health NAME="Machine Health"`.
$plugin = \App\Models\Plugin::where('name', getenv('PLUGIN_NAME'))->firstOrFail();
$plugin->update(['render_markup' => file_get_contents('/tmp/plugin-template.liquid'), 'current_image' => null]);
$device = \App\Models\Device::firstOrFail();
$uuid = \App\Services\ImageGenerationService::generateImage($plugin->render('full', true, $device), $device->id, $plugin);
$plugin->update(['current_image' => $uuid]);
echo "PREVIEW ".$uuid."\n";
