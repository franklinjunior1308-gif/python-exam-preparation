import 'package:material_ui/material_ui.dart';

/// Dark Tech palette shared with the web app: navy surfaces, cyan primary, blue accent.
class Fx {
  static const bg = Color(0xFF07162B);
  static const bg2 = Color(0xFF0B1F3B);
  static const surface = Color(0xFF0F2A4A);
  static const surface2 = Color(0xFF133458);
  static const primary = Color(0xFF06D6FF);
  static const accent = Color(0xFF3A86FF);
  static const text = Color(0xFFE6EEF8);
  static const muted = Color(0xFF8FA6C4);
  static const line = Color(0x33789AE6);
  static const danger = Color(0xFFFF6B7A);
  static const ok = Color(0xFF34D399);
  static const warn = Color(0xFFFBBF24);
  static const violet = Color(0xFF8B7BFF);
  static const orange = Color(0xFFFB923C);

  static Color statusColor(String status) => switch (status) {
    'SCHEDULED' => accent,
    'ACCEPTED' => violet,
    'IN_PROGRESS' => warn,
    'BLOCKED' => orange,
    'COMPLETED' => ok,
    _ => muted,
  };

  static Color priorityColor(String priority) => switch (priority) {
    'HIGH' => danger,
    'NORMAL' => warn,
    _ => ok,
  };
}

ThemeData buildTheme() {
  final scheme =
      ColorScheme.fromSeed(
        seedColor: Fx.primary,
        brightness: Brightness.dark,
      ).copyWith(
        primary: Fx.primary,
        onPrimary: const Color(0xFF031C26),
        secondary: Fx.accent,
        surface: Fx.surface,
        onSurface: Fx.text,
        error: Fx.danger,
      );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: Fx.bg,
    appBarTheme: const AppBarTheme(
      backgroundColor: Fx.bg,
      foregroundColor: Fx.text,
      elevation: 0,
      centerTitle: false,
    ),
  );
}
