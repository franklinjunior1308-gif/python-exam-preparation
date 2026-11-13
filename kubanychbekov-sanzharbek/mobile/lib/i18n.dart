import 'package:intl/intl.dart';
import 'package:timezone/timezone.dart' as tz;

/// UI strings. English is complete; Russian mirrors it key for key (a test checks parity).
const Map<String, String> en = {
  'app.name': 'FixFlow Technician',
  'common.cancel': 'Cancel',
  'common.confirm': 'Confirm',
  'common.delete': 'Delete',
  'common.retry': 'Retry',
  'common.back': 'Back',
  'common.save': 'Save',
  'common.loading': 'Loading...',
  'common.none': 'None',
  'login.title': 'Sign in',
  'login.subtitle': 'Continue working with your assigned tasks',
  'login.email': 'Email',
  'login.password': 'Password',
  'login.server': 'Server address',
  'login.serverHint':
      'Emulator: http://10.0.2.2:8000. Phone: http://<computer IP>:8000',
  'login.submit': 'Sign in',
  'login.demo': 'Demo technician accounts (demo environment only)',
  'login.expired':
      'Your session has expired. Sign in again; your queued work is safe.',
  'login.noTechnicianRole':
      'This account has no technician role in any organization.',
  'org.title': 'Choose an organization',
  'org.subtitle': 'Pick the organization you work in today',
  'tabs.tasks': 'Tasks',
  'tabs.queue': 'Queue',
  'tabs.notifications': 'Alerts',
  'tabs.profile': 'Profile',
  'tasks.title': 'My tasks',
  'tasks.active': 'Active',
  'tasks.today': 'Today',
  'tasks.done': 'Completed',
  'tasks.empty': 'No tasks here yet.',
  'tasks.lastSync': 'Last synced {time}',
  'tasks.neverSynced': 'Not synced yet',
  'offline.banner': 'Offline mode. Tasks are read from this phone and your work is saved locally.',
  'offline.sync': 'Sync ({n})',
  'offline.onlineOnly': 'This action needs a connection to the server.',
  'status.SCHEDULED': 'Assigned',
  'status.ACCEPTED': 'Accepted',
  'status.IN_PROGRESS': 'In progress',
  'status.BLOCKED': 'Blocked',
  'status.COMPLETED': 'Completed',
  'priority.LOW': 'Low',
  'priority.NORMAL': 'Normal',
  'priority.HIGH': 'High',
  'detail.title': 'Request #{id}',
  'detail.customer': 'Customer',
  'detail.property': 'Property',
  'detail.visit': 'Visit',
  'detail.equipment': 'Equipment',
  'detail.contact': 'Contact notes',
  'detail.description': 'Description',
  'detail.actions': 'Actions',
  'detail.work': 'Work on site',
  'detail.notes': 'Notes',
  'detail.photos': 'Photos',
  'detail.noNotes': 'No notes yet.',
  'detail.noPhotos': 'No photos yet.',
  'detail.waiting': 'Waiting to sync',
  'action.accept': 'Accept task',
  'action.decline': 'Decline',
  'action.start': 'Start work',
  'action.block': 'Mark as blocked',
  'action.resume': 'Resume work',
  'action.complete': 'Complete work',
  'action.addNote': 'Add note',
  'action.addPhoto': 'Add photo',
  'action.reason': 'Reason',
  'action.reasonRequired': 'A reason is required.',
  'action.declineTitle': 'Decline this task?',
  'action.declineText':
      'The dispatcher will be told and the task will be reassigned.',
  'action.done': 'Done',
  'note.title': 'New note',
  'note.hint': 'What did you find or do?',
  'note.internal': 'Internal (not visible to the customer)',
  'note.saved': 'Note saved on this phone and will be sent automatically.',
  'photo.title': 'Add photo',
  'photo.camera': 'Take a photo',
  'photo.gallery': 'Choose from gallery',
  'photo.before': 'Before',
  'photo.after': 'After',
  'photo.saved':
      'Photo saved on this phone and will be uploaded automatically.',
  'complete.title': 'Complete work',
  'complete.summary': 'Final note',
  'complete.summaryHint':
      'At least 20 characters: what was done, results, remaining issues.',
  'complete.photos': 'Photos on the server: {n}. Waiting to sync: {m}.',
  'complete.needSync': 'Waiting photos must reach the server first. Open the Queue tab and sync.',
  'complete.submit': 'Complete work',
  'complete.successTitle': 'Work completed!',
  'complete.successText': 'Request #{id} was completed and sent to the system.',
  'complete.toTasks': 'Back to tasks',
  'queue.title': 'Offline queue',
  'queue.empty': 'Nothing is waiting to be sent.',
  'queue.pending': 'Pending sync',
  'queue.failed': 'Failed',
  'queue.conflict': 'Conflict',
  'queue.note': 'Note',
  'queue.photo': 'Photo',
  'queue.queuedAt': 'Queued {time}',
  'queue.syncNow': 'Sync now',
  'queue.conflictHelp': 'The request changed while you were offline. Your draft is kept until you decide.',
  'queue.deleteTitle': 'Delete this item?',
  'queue.deleteText': 'It has not been delivered and will be lost.',
  'queue.synced': 'Sent {n} item(s).',
  'queue.conflicts': '{n} item(s) need your decision.',
  'notif.title': 'Notifications',
  'notif.empty': 'No notifications.',
  'notif.markRead': 'Mark all read',
  'profile.title': 'Profile',
  'profile.org': 'Organization',
  'profile.switchOrg': 'Switch organization',
  'profile.role': 'Role',
  'profile.technician': 'Technician',
  'profile.language': 'Language',
  'profile.server': 'Server',
  'profile.signOut': 'Sign out',
  'profile.signOutWarn':
      '{n} item(s) are still waiting to be sent. They stay on this phone.',
  'err.network': 'Cannot reach the server. Check your connection.',
  'err.invalid_credentials': 'Wrong email or password.',
  'err.account_disabled': 'This account is disabled.',
  'err.session_expired': 'Your session has expired.',
  'err.invalid_token': 'Your session has expired.',
  'err.not_a_member': 'You do not have access to this organization.',
  'err.state_conflict':
      'The task was changed by someone else. Refresh and try again.',
  'err.transition_forbidden': 'You are not allowed to do this.',
  'err.invalid_transition': 'This is not possible from the current status.',
  'err.reason_required': 'A reason is required.',
  'err.summary_too_short': 'The final note needs at least 20 characters.',
  'err.photo_required': 'Upload at least one photo before completing.',
  'err.assignment_changed': 'This task is no longer assigned to you.',
  'err.request_closed': 'This request is closed.',
  'err.invalid_image': 'The file is not a valid image.',
  'err.unsupported_image_type': 'Only JPEG, PNG and WebP photos are accepted.',
  'err.file_too_large': 'The photo is larger than 10 MB.',
  'err.file_missing': 'The photo file is no longer on the phone.',
  'err.work_started': 'Work has already started.',
  'err.estimate_not_approved':
      'The customer must approve the estimate before work can start.',
  'action.materials': 'Used materials',
  'materials.title': 'Used materials',
  'materials.search': 'Search material',
  'materials.stock': 'In stock: {n} {unit}',
  'materials.low': 'low stock',
  'materials.used': 'Already written off',
  'materials.none': 'Nothing written off yet.',
  'materials.noMatches': 'No materials match.',
  'materials.quantity': 'Quantity ({unit})',
  'materials.writeOff': 'Write off',
  'materials.done': 'Written off.',
  'materials.badQuantity': 'Enter a positive number (up to 3 decimals).',
  'detail.estimate': 'Approved estimate',
  'err.insufficient_stock': 'Not enough of this material in stock.',
  'err.work_not_in_progress':
      'Materials can be written off only while work is in progress.',
  'err.idempotency_conflict':
      'This write-off was already recorded differently. Reload and check.',
  'err.item_not_found': 'Material not found.',
  'err.too_many_attempts':
      'Too many failed sign-in attempts. Wait a few minutes and try again.',
  'notif.assignment_created': 'New task: request #{id}',
  'notif.assignment_rescheduled': 'Task changed: request #{id}',
  'notif.assignment_canceled': 'Task removed: request #{id}',
  'notif.assignment_declined': 'Technician declined request #{id}',
  'notif.request_completed': 'Request #{id} was completed',
  'notif.sla_overdue': 'Request #{id} is past its SLA',
  'notif.estimate_submitted': 'Estimate for request #{id} awaits your decision',
  'err.generic': 'The operation failed. Please try again.',
};

const Map<String, String> ru = {
  'app.name': 'FixFlow Техник',
  'common.cancel': 'Отмена',
  'common.confirm': 'Подтвердить',
  'common.delete': 'Удалить',
  'common.retry': 'Повторить',
  'common.back': 'Назад',
  'common.save': 'Сохранить',
  'common.loading': 'Загрузка...',
  'common.none': 'Нет',
  'login.title': 'Вход в систему',
  'login.subtitle': 'Продолжайте работу с назначенными заданиями',
  'login.email': 'Email',
  'login.password': 'Пароль',
  'login.server': 'Адрес сервера',
  'login.serverHint':
      'Эмулятор: http://10.0.2.2:8000. Телефон: http://<IP компьютера>:8000',
  'login.submit': 'Войти',
  'login.demo': 'Демо-аккаунты техников (только для демо-среды)',
  'login.expired': 'Сессия истекла. Войдите снова, очередь не потеряна.',
  'login.noTechnicianRole':
      'У этой учётной записи нет роли техника ни в одной организации.',
  'org.title': 'Выберите организацию',
  'org.subtitle': 'Выберите организацию, в которой работаете сегодня',
  'tabs.tasks': 'Задания',
  'tabs.queue': 'Очередь',
  'tabs.notifications': 'События',
  'tabs.profile': 'Профиль',
  'tasks.title': 'Мои задания',
  'tasks.active': 'Активные',
  'tasks.today': 'Сегодня',
  'tasks.done': 'Завершённые',
  'tasks.empty': 'Здесь пока нет заданий.',
  'tasks.lastSync': 'Синхронизировано {time}',
  'tasks.neverSynced': 'Ещё не синхронизировано',
  'offline.banner': 'Офлайн-режим. Задания читаются с телефона, ваша работа сохраняется локально.',
  'offline.sync': 'Синхронизировать ({n})',
  'offline.onlineOnly': 'Для этого действия нужно подключение к серверу.',
  'status.SCHEDULED': 'Назначено',
  'status.ACCEPTED': 'Принято',
  'status.IN_PROGRESS': 'В работе',
  'status.BLOCKED': 'Заблокировано',
  'status.COMPLETED': 'Выполнено',
  'priority.LOW': 'Низкий',
  'priority.NORMAL': 'Средний',
  'priority.HIGH': 'Высокий',
  'detail.title': 'Заявка #{id}',
  'detail.customer': 'Заказчик',
  'detail.property': 'Объект',
  'detail.visit': 'Визит',
  'detail.equipment': 'Оборудование',
  'detail.contact': 'Как связаться',
  'detail.description': 'Описание',
  'detail.actions': 'Действия',
  'detail.work': 'Работа на объекте',
  'detail.notes': 'Заметки',
  'detail.photos': 'Фото',
  'detail.noNotes': 'Заметок пока нет.',
  'detail.noPhotos': 'Фото пока нет.',
  'detail.waiting': 'Ожидает синхронизации',
  'action.accept': 'Принять задание',
  'action.decline': 'Отказаться',
  'action.start': 'Начать выполнение',
  'action.block': 'Отметить заблокированным',
  'action.resume': 'Продолжить работу',
  'action.complete': 'Завершить работу',
  'action.addNote': 'Добавить заметку',
  'action.addPhoto': 'Добавить фото',
  'action.reason': 'Причина',
  'action.reasonRequired': 'Нужно указать причину.',
  'action.declineTitle': 'Отказаться от задания?',
  'action.declineText':
      'Диспетчер получит уведомление, задание будет назначено другому.',
  'action.done': 'Готово',
  'note.title': 'Новая заметка',
  'note.hint': 'Что вы обнаружили или сделали?',
  'note.internal': 'Внутренняя (заказчик не видит)',
  'note.saved':
      'Заметка сохранена на телефоне и будет отправлена автоматически.',
  'photo.title': 'Добавить фото',
  'photo.camera': 'Сделать снимок',
  'photo.gallery': 'Выбрать из галереи',
  'photo.before': 'До',
  'photo.after': 'После',
  'photo.saved': 'Фото сохранено на телефоне и будет загружено автоматически.',
  'complete.title': 'Завершение работы',
  'complete.summary': 'Итоговая заметка',
  'complete.summaryHint':
      'Не менее 20 символов: что сделано, результат, что осталось.',
  'complete.photos': 'Фото на сервере: {n}. Ожидают синхронизации: {m}.',
  'complete.needSync': 'Сначала фото должны дойти до сервера. Откройте «Очередь» и синхронизируйте.',
  'complete.submit': 'Завершить работу',
  'complete.successTitle': 'Работа выполнена!',
  'complete.successText': 'Заявка #{id} завершена и отправлена в систему.',
  'complete.toTasks': 'К заданиям',
  'queue.title': 'Офлайн-очередь',
  'queue.empty': 'Ничего не ждёт отправки.',
  'queue.pending': 'Ожидает синхронизации',
  'queue.failed': 'Ошибка',
  'queue.conflict': 'Конфликт',
  'queue.note': 'Заметка',
  'queue.photo': 'Фото',
  'queue.queuedAt': 'В очереди с {time}',
  'queue.syncNow': 'Синхронизировать',
  'queue.conflictHelp': 'Заявка изменилась, пока вы были офлайн. Черновик хранится, пока вы не решите.',
  'queue.deleteTitle': 'Удалить элемент?',
  'queue.deleteText': 'Он не доставлен и будет потерян.',
  'queue.synced': 'Отправлено элементов: {n}.',
  'queue.conflicts': 'Требуют вашего решения: {n}.',
  'notif.title': 'Уведомления',
  'notif.empty': 'Уведомлений нет.',
  'notif.markRead': 'Прочитать все',
  'profile.title': 'Профиль',
  'profile.org': 'Организация',
  'profile.switchOrg': 'Сменить организацию',
  'profile.role': 'Роль',
  'profile.technician': 'Техник',
  'profile.language': 'Язык',
  'profile.server': 'Сервер',
  'profile.signOut': 'Выйти',
  'profile.signOutWarn':
      'Ещё не отправлено элементов: {n}. Они останутся на телефоне.',
  'err.network': 'Нет связи с сервером. Проверьте подключение.',
  'err.invalid_credentials': 'Неверный email или пароль.',
  'err.account_disabled': 'Эта учётная запись отключена.',
  'err.session_expired': 'Сессия истекла.',
  'err.invalid_token': 'Сессия истекла.',
  'err.not_a_member': 'У вас нет доступа к этой организации.',
  'err.state_conflict': 'Задание изменил кто-то другой. Обновите и повторите.',
  'err.transition_forbidden': 'У вас нет прав на это действие.',
  'err.invalid_transition': 'Это невозможно из текущего статуса.',
  'err.reason_required': 'Нужно указать причину.',
  'err.summary_too_short':
      'Итоговая заметка должна быть не короче 20 символов.',
  'err.photo_required': 'Перед завершением загрузите хотя бы одно фото.',
  'err.assignment_changed': 'Это задание больше не назначено вам.',
  'err.request_closed': 'Заявка закрыта.',
  'err.invalid_image': 'Файл не является изображением.',
  'err.unsupported_image_type': 'Принимаются только JPEG, PNG и WebP.',
  'err.file_too_large': 'Фото больше 10 МБ.',
  'err.file_missing': 'Файла фото больше нет на телефоне.',
  'err.work_started': 'Работа уже началась.',
  'err.estimate_not_approved':
      'Заказчик должен одобрить смету, прежде чем можно начать работу.',
  'action.materials': 'Использованные материалы',
  'materials.title': 'Использованные материалы',
  'materials.search': 'Поиск материала',
  'materials.stock': 'На складе: {n} {unit}',
  'materials.low': 'мало на складе',
  'materials.used': 'Уже списано',
  'materials.none': 'Пока ничего не списано.',
  'materials.noMatches': 'Подходящих материалов нет.',
  'materials.quantity': 'Количество ({unit})',
  'materials.writeOff': 'Списать',
  'materials.done': 'Списано.',
  'materials.badQuantity':
      'Введите положительное число (до 3 знаков после запятой).',
  'detail.estimate': 'Одобренная смета',
  'err.insufficient_stock':
      'Этого материала нет в нужном количестве на складе.',
  'err.work_not_in_progress':
      'Материалы списываются только пока работа выполняется.',
  'err.idempotency_conflict':
      'Это списание уже записано иначе. Обновите и проверьте.',
  'err.item_not_found': 'Материал не найден.',
  'err.too_many_attempts':
      'Слишком много неудачных попыток входа. Подождите несколько минут.',
  'notif.assignment_created': 'Новое задание: заявка #{id}',
  'notif.assignment_rescheduled': 'Задание изменено: заявка #{id}',
  'notif.assignment_canceled': 'Задание снято: заявка #{id}',
  'notif.assignment_declined': 'Техник отказался от заявки #{id}',
  'notif.request_completed': 'Заявка #{id} выполнена',
  'notif.sla_overdue': 'Заявка #{id} просрочена по SLA',
  'notif.estimate_submitted': 'Смета по заявке #{id} ждёт вашего решения',
  'err.generic': 'Операция не удалась. Повторите попытку.',
};

String tr(String lang, String key, [Map<String, Object?>? params]) {
  var text = (lang == 'ru' ? ru : en)[key] ?? en[key] ?? key;
  params?.forEach((name, value) => text = text.replaceAll('{$name}', '$value'));
  return text;
}

/// Notification titles are system text written by the server in English. Known types are shown in
/// the user's language; anything else keeps the server text. The body is user data (a request
/// title or a reason) and is never translated.
String trNotificationTitle(
  String lang,
  String type,
  int? requestId,
  String serverTitle,
) {
  final key = 'notif.$type';
  if (requestId == null || !en.containsKey(key)) return serverTitle;
  return tr(lang, key, {'id': requestId});
}

/// Backend error code -> translated message, with a safe fallback.
String trError(String lang, String code) {
  final key = 'err.$code';
  return en.containsKey(key) ? tr(lang, key) : tr(lang, 'err.generic');
}

/// Show a UTC instant in the organization's timezone (DATA-03), never the phone's zone.
String formatWhen(
  DateTime utc,
  String timezone,
  String lang, {
  bool dateOnly = false,
}) {
  final tz.Location location = tz.getLocation(timezone);
  final local = tz.TZDateTime.from(utc, location);
  final locale = lang == 'ru' ? 'ru' : 'en_GB';
  return dateOnly
      ? DateFormat('d MMM', locale).format(local)
      : DateFormat('d MMM, HH:mm', locale).format(local);
}

String formatRange(DateTime start, DateTime end, String timezone, String lang) {
  final location = tz.getLocation(timezone);
  final s = tz.TZDateTime.from(start, location);
  final e = tz.TZDateTime.from(end, location);
  final clock = DateFormat('HH:mm');
  return '${formatWhen(start, timezone, lang)} - ${clock.format(e)}'
      '${s.day == e.day ? '' : ' (+1)'}';
}

/// "2026-11-12" of an instant in the organization's timezone.
String localDay(DateTime utc, String timezone) {
  final local = tz.TZDateTime.from(utc, tz.getLocation(timezone));
  return DateFormat('yyyy-MM-dd').format(local);
}
