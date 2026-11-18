<?php
// Uploads plugins/<dir>/template.liquid into the plugin named $PLUGIN_NAME and renders a preview PNG.
// A missing plugin is created; plugins/<dir>/plugin.json (optional) sets its data source and
// settings fields, otherwise it is a webhook plugin.
// Run through `make plugin-deploy DIR=machine-health NAME="Machine Health"`.
$plugin = \App\Models\Plugin::firstOrNew(['name' => getenv('PLUGIN_NAME'), 'user_id' => \App\Models\User::firstOrFail()->id]);
if (! $plugin->exists) {
    $plugin->fill(['data_strategy' => 'webhook', 'data_stale_minutes' => 5, 'markup_language' => 'liquid', 'plugin_type' => 'recipe']);
}
if (is_file('/tmp/plugin-settings.json')) {
    $settings = json_decode(file_get_contents('/tmp/plugin-settings.json'), true, 512, JSON_THROW_ON_ERROR);
    $plugin->fill($settings);
    foreach ($settings['configuration_template']['custom_fields'] ?? [] as $field) {
        if (isset($field['default']) && ! isset($plugin->configuration[$field['keyname']])) {
            $plugin->configuration = array_merge($plugin->configuration ?? [], [$field['keyname'] => $field['default']]);
        }
    }
}
$plugin->fill(['render_markup' => file_get_contents('/tmp/plugin-template.liquid'), 'current_image' => null])->save();
if ($plugin->data_strategy === 'polling') {
    $plugin->updateDataPayload();
    $plugin->refresh();
}
$device = \App\Models\Device::first();
if ($device) {
    $uuid = \App\Services\ImageGenerationService::generateImage($plugin->render('full', true, $device), $device->id, $plugin);
    $plugin->update(['current_image' => $uuid]);
    echo "PREVIEW ".$uuid."\n";
} else {
    echo "DEPLOYED without preview (no device yet)\n";
}
if ($plugin->data_strategy === 'webhook') {
    echo "WEBHOOK /api/custom_plugins/".$plugin->uuid."\n";
}
