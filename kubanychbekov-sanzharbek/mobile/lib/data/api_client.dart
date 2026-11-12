import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Error returned by the FixFlow API, or a network failure (status 0).
class ApiException implements Exception {
  ApiException(this.status, this.code, this.message);

  final int status;
  final String code;
  final String message;

  bool get isNetwork => status == 0;
  bool get isUnauthorized => status == 401;

  /// The job changed under the user's feet while offline (MOB-07).
  bool get isConflict =>
      status == 409 &&
      (code == 'assignment_changed' || code == 'request_closed');

  @override
  String toString() => 'ApiException($status, $code, $message)';
}

/// Thin HTTP client for the FastAPI backend. It never throws raw socket errors: connection
/// problems become `ApiException(0, 'network')`, so callers can tell "offline" from "refused".
class ApiClient {
  ApiClient({
    required String baseUrl,
    required this.client,
    this.token,
    this.orgId,
    this.timeout = const Duration(seconds: 15),
  }) : baseUrl = baseUrl.replaceAll(RegExp(r'/+$'), '');

  final String baseUrl;
  final http.Client client;
  final String? token;
  final int? orgId;
  final Duration timeout;

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl/api/v1/$path').replace(queryParameters: query);

  Map<String, String> get _headers => {
    if (token != null) 'Authorization': 'Bearer $token',
    if (orgId != null) 'X-Organization-Id': '$orgId',
  };

  /// URL and headers for loading an image with Image.network.
  Uri fileUri(int attachmentId) => _uri('attachments/$attachmentId/file');
  Map<String, String> get imageHeaders => _headers;

  Future<dynamic> get(String path, {Map<String, String>? query}) =>
      _send(() => client.get(_uri(path, query), headers: _headers));

  Future<dynamic> post(String path, {Object? body}) => _send(
    () => client.post(
      _uri(path),
      headers: {..._headers, 'Content-Type': 'application/json'},
      body: jsonEncode(body ?? {}),
    ),
  );

  /// Uploads one image file with the same stable `client_command_id` on every attempt.
  Future<dynamic> postFile(
    String path, {
    required String filePath,
    required Map<String, String> fields,
  }) => _send(() async {
    final request = http.MultipartRequest('POST', _uri(path))
      ..headers.addAll(_headers)
      ..fields.addAll(fields)
      ..files.add(await http.MultipartFile.fromPath('file', filePath));
    return http.Response.fromStream(await client.send(request));
  });

  Future<dynamic> _send(Future<http.Response> Function() call) async {
    final http.Response response;
    try {
      response = await call().timeout(timeout);
    } on TimeoutException {
      throw ApiException(0, 'network', 'The server did not answer in time');
    } on SocketException {
      throw ApiException(0, 'network', 'No connection to the server');
    } on http.ClientException {
      throw ApiException(0, 'network', 'No connection to the server');
    } on FileSystemException {
      // not a network problem: retrying can never help, so it must not look like "offline"
      throw ApiException(
        400,
        'file_missing',
        'The photo file is no longer on the phone',
      );
    }

    final text = utf8.decode(response.bodyBytes);
    dynamic payload;
    if (text.isNotEmpty) {
      try {
        payload = jsonDecode(text);
      } on FormatException {
        payload = null;
      }
    }
    if (response.statusCode >= 200 && response.statusCode < 300) return payload;

    final error = payload is Map ? payload['error'] : null;
    throw ApiException(
      response.statusCode,
      error is Map ? (error['code'] as String? ?? 'error') : 'error',
      error is Map
          ? (error['message'] as String? ?? 'Request failed')
          : 'Request failed',
    );
  }
}
