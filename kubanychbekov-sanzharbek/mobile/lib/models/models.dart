// Plain data classes shared by storage, network and UI. Everything is JSON-serializable so it
// can be kept in the local database and rebuilt after the app restarts (MOB-04).

const activeAssignmentStatuses = ['SCHEDULED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED'];

class Membership {
  Membership({
    required this.organizationId,
    required this.organizationName,
    required this.timezone,
    required this.role,
  });

  final int organizationId;
  final String organizationName;
  final String timezone;
  final String role;

  factory Membership.fromJson(Map<String, dynamic> json) => Membership(
        organizationId: json['organization_id'] as int,
        organizationName: json['organization_name'] as String,
        timezone: json['timezone'] as String,
        role: json['role'] as String,
      );

  Map<String, dynamic> toJson() => {
        'organization_id': organizationId,
        'organization_name': organizationName,
        'timezone': timezone,
        'role': role,
      };
}

/// What we remember about the signed-in user. The token is kept so queued work survives restarts.
class Session {
  Session({
    required this.serverUrl,
    required this.token,
    required this.userName,
    required this.email,
    required this.memberships,
    this.orgId,
    this.needsLogin = false,
  });

  final String serverUrl;
  final String token;
  final String userName;
  final String email;
  final List<Membership> memberships;
  final int? orgId;

  /// Set when the server rejected the token. The queue and cached tasks are kept (AUTH-04).
  final bool needsLogin;

  Membership? get membership {
    for (final m in memberships) {
      if (m.organizationId == orgId) return m;
    }
    return null;
  }

  Session copyWith({String? token, int? orgId, bool? needsLogin, String? serverUrl}) => Session(
        serverUrl: serverUrl ?? this.serverUrl,
        token: token ?? this.token,
        userName: userName,
        email: email,
        memberships: memberships,
        orgId: orgId ?? this.orgId,
        needsLogin: needsLogin ?? this.needsLogin,
      );

  factory Session.fromJson(Map<String, dynamic> json) => Session(
        serverUrl: json['server_url'] as String,
        token: json['token'] as String,
        userName: json['user_name'] as String,
        email: json['email'] as String,
        memberships: (json['memberships'] as List)
            .map((e) => Membership.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        orgId: json['org_id'] as int?,
        needsLogin: json['needs_login'] as bool? ?? false,
      );

  Map<String, dynamic> toJson() => {
        'server_url': serverUrl,
        'token': token,
        'user_name': userName,
        'email': email,
        'memberships': memberships.map((m) => m.toJson()).toList(),
        'org_id': orgId,
        'needs_login': needsLogin,
      };
}

class Task {
  Task({
    required this.assignmentId,
    required this.assignmentStatus,
    required this.startAt,
    required this.endAt,
    required this.timezone,
    required this.requestId,
    required this.title,
    required this.description,
    required this.priority,
    required this.requestStatus,
    required this.allowedActions,
    required this.categoryName,
    required this.propertyName,
    required this.propertyAddress,
    required this.customerName,
    required this.updatedAt,
    this.contactInstructions,
    this.assetLabel,
  });

  final int assignmentId;
  final String assignmentStatus;
  final DateTime startAt;
  final DateTime endAt;
  final String timezone;
  final int requestId;
  final String title;
  final String description;
  final String priority;
  final String requestStatus;
  final List<String> allowedActions;
  final String categoryName;
  final String propertyName;
  final String propertyAddress;
  final String? contactInstructions;
  final String? assetLabel;
  final String customerName;
  final DateTime updatedAt;

  bool get isActive => activeAssignmentStatuses.contains(assignmentStatus);
  bool get isDone => assignmentStatus == 'COMPLETED';

  factory Task.fromJson(Map<String, dynamic> json) => Task(
        assignmentId: json['assignment_id'] as int,
        assignmentStatus: json['assignment_status'] as String,
        startAt: DateTime.parse(json['start_at'] as String).toUtc(),
        endAt: DateTime.parse(json['end_at'] as String).toUtc(),
        timezone: json['timezone'] as String,
        requestId: json['request_id'] as int,
        title: json['title'] as String,
        description: json['description'] as String,
        priority: json['priority'] as String,
        requestStatus: json['request_status'] as String,
        allowedActions: (json['allowed_actions'] as List).cast<String>(),
        categoryName: json['category_name'] as String,
        propertyName: json['property_name'] as String,
        propertyAddress: json['property_address'] as String,
        contactInstructions: json['contact_instructions'] as String?,
        assetLabel: json['asset_label'] as String?,
        customerName: json['customer_name'] as String,
        updatedAt: DateTime.parse(json['updated_at'] as String).toUtc(),
      );

  Map<String, dynamic> toJson() => {
        'assignment_id': assignmentId,
        'assignment_status': assignmentStatus,
        'start_at': startAt.toIso8601String(),
        'end_at': endAt.toIso8601String(),
        'timezone': timezone,
        'request_id': requestId,
        'title': title,
        'description': description,
        'priority': priority,
        'request_status': requestStatus,
        'allowed_actions': allowedActions,
        'category_name': categoryName,
        'property_name': propertyName,
        'property_address': propertyAddress,
        'contact_instructions': contactInstructions,
        'asset_label': assetLabel,
        'customer_name': customerName,
        'updated_at': updatedAt.toIso8601String(),
      };
}

enum QueueType { note, photo }

/// pending  - waiting for a connection (or the next sync round)
/// failed   - the server refused it for a fixable reason; the user may retry or delete
/// conflict - the job changed while the phone was offline; kept until the user decides (MOB-07)
enum QueueState { pending, failed, conflict }

class QueueItem {
  QueueItem({
    required this.id,
    required this.type,
    required this.requestId,
    required this.createdAt,
    this.body,
    this.visibility = 'public',
    this.filePath,
    this.purpose = 'evidence',
    this.state = QueueState.pending,
    this.attempts = 0,
    this.error,
    this.conflictCode,
  });

  /// Stable client command id. Sent with every attempt so the server stores the work only once
  /// even if a response was lost and the item is delivered again (MOB-06).
  final String id;
  final QueueType type;
  final int requestId;
  final DateTime createdAt;
  final String? body;
  final String visibility;
  final String? filePath;
  final String purpose;
  final QueueState state;
  final int attempts;
  final String? error;
  final String? conflictCode;

  QueueItem copyWith({QueueState? state, int? attempts, String? error, String? conflictCode}) =>
      QueueItem(
        id: id,
        type: type,
        requestId: requestId,
        createdAt: createdAt,
        body: body,
        visibility: visibility,
        filePath: filePath,
        purpose: purpose,
        state: state ?? this.state,
        attempts: attempts ?? this.attempts,
        error: error ?? this.error,
        conflictCode: conflictCode ?? this.conflictCode,
      );

  factory QueueItem.fromJson(Map<String, dynamic> json) => QueueItem(
        id: json['id'] as String,
        type: QueueType.values.byName(json['type'] as String),
        requestId: json['request_id'] as int,
        createdAt: DateTime.parse(json['created_at'] as String),
        body: json['body'] as String?,
        visibility: json['visibility'] as String? ?? 'public',
        filePath: json['file_path'] as String?,
        purpose: json['purpose'] as String? ?? 'evidence',
        state: QueueState.values.byName(json['state'] as String? ?? 'pending'),
        attempts: json['attempts'] as int? ?? 0,
        error: json['error'] as String?,
        conflictCode: json['conflict_code'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type.name,
        'request_id': requestId,
        'created_at': createdAt.toIso8601String(),
        'body': body,
        'visibility': visibility,
        'file_path': filePath,
        'purpose': purpose,
        'state': state.name,
        'attempts': attempts,
        'error': error,
        'conflict_code': conflictCode,
      };
}

class NotificationItem {
  NotificationItem({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.createdAt,
    this.requestId,
    this.readAt,
  });

  final int id;
  final String type;
  final String title;
  final String body;
  final DateTime createdAt;
  final int? requestId;
  final DateTime? readAt;

  bool get unread => readAt == null;

  factory NotificationItem.fromJson(Map<String, dynamic> json) => NotificationItem(
        id: json['id'] as int,
        type: json['type'] as String,
        title: json['title'] as String,
        body: json['body'] as String? ?? '',
        requestId: json['request_id'] as int?,
        createdAt: DateTime.parse(json['created_at'] as String).toUtc(),
        readAt: json['read_at'] == null ? null : DateTime.parse(json['read_at'] as String),
      );
}

class RemoteNote {
  RemoteNote({
    required this.id,
    required this.author,
    required this.body,
    required this.visibility,
    required this.kind,
    required this.createdAt,
  });

  final int id;
  final String author;
  final String body;
  final String visibility;
  final String kind;
  final DateTime createdAt;

  factory RemoteNote.fromJson(Map<String, dynamic> json) => RemoteNote(
        id: json['id'] as int,
        author: json['author_name'] as String? ?? '',
        body: json['body'] as String,
        visibility: json['visibility'] as String,
        kind: json['kind'] as String,
        createdAt: DateTime.parse(json['created_at'] as String).toUtc(),
      );
}

class RemoteAttachment {
  RemoteAttachment({required this.id, required this.purpose, required this.createdAt});

  final int id;
  final String purpose;
  final DateTime createdAt;

  factory RemoteAttachment.fromJson(Map<String, dynamic> json) => RemoteAttachment(
        id: json['id'] as int,
        purpose: json['purpose'] as String,
        createdAt: DateTime.parse(json['created_at'] as String).toUtc(),
      );
}
