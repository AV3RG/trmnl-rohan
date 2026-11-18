<?php
// Writes the server's configuration (plugins, their non-secret settings, playlist, device) to
// /tmp/server-export.json. Secrets (password fields, device API key) are never exported.
// Run through `make config-export`.
use App\Models\{Device, Playlist, Plugin, User};

$previous = is_file('/tmp/server.json') ? json_decode(file_get_contents('/tmp/server.json'), true) : [];
$sources = collect($previous['plugins'] ?? [])->pluck('source', 'name');
$user = User::firstOrFail();

$plugins = Plugin::where('user_id', $user->id)->orderBy('id')->get()->map(function (Plugin $plugin) use ($sources) {
    $secretKeys = collect($plugin->configuration_template['custom_fields'] ?? [])
        ->where('field_type', 'password')->pluck('keyname')->all();
    $source = $sources[$plugin->name] ?? null;
    $entry = [
        'name' => $plugin->name,
        'source' => $source,
        'settings' => collect($plugin->configuration ?? [])->except($secretKeys)->all() ?: new stdClass,
        'secrets' => $secretKeys,
        'data_stale_minutes' => $plugin->data_stale_minutes,
    ];
    // Imported plugins: keep the data source too, since some were edited after import.
    if (! isset($source['dir'])) {
        $entry['polling'] = $plugin->only(['polling_url', 'polling_verb', 'polling_header', 'polling_body']);
    }
    if ($source === null) {
        fwrite(STDERR, "WARNING: no source recorded for \"{$plugin->name}\"; add one to config/server.json\n");
    }

    return $entry;
})->all();

$device = Device::where('user_id', $user->id)->first();
$playlists = $device ? Playlist::where('device_id', $device->id)->get()->map(fn (Playlist $playlist) => [
    'name' => $playlist->name,
    'is_active' => (bool) $playlist->is_active,
    'refresh_time' => $playlist->refresh_time,
    'items' => $playlist->items()->orderBy('order')->get()
        ->map(fn ($item) => ['plugin' => $item->plugin?->name, 'is_active' => (bool) $item->is_active])
        ->filter(fn ($item) => $item['plugin'] !== null)->values()->all(),
])->all() : [];

file_put_contents('/tmp/server-export.json', json_encode([
    'timezone' => $user->timezone,
    'device' => $device?->only(['name', 'mac_address', 'default_refresh_interval', 'width', 'height']),
    'playlists' => $playlists,
    'plugins' => $plugins,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)."\n");
echo "EXPORTED ".count($plugins)." plugins\n";
