import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../theme/app_theme.dart';
import 'notification_service.dart';

class NotificationsCenterScreen extends StatefulWidget {
  const NotificationsCenterScreen({
    super.key,
    required this.service,
  });

  final NotificationService service;

  @override
  State<NotificationsCenterScreen> createState() =>
      _NotificationsCenterScreenState();
}

class _NotificationsCenterScreenState extends State<NotificationsCenterScreen> {
  bool _isLoading = false;
  String? _error;
  List<NotificationItem> _items = const <NotificationItem>[];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_isLoading) {
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final items = await widget.service.fetchAll(limit: 40);
      if (!mounted) {
        return;
      }
      setState(() {
        _items = items;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _markRead(NotificationItem item) async {
    if (!item.isUnread) {
      return;
    }
    try {
      await widget.service.markRead(item.notificationId);
      if (!mounted) {
        return;
      }
      setState(() {
        _items = _items
            .map(
              (current) => current.notificationId == item.notificationId
                  ? NotificationItem(
                      notificationId: current.notificationId,
                      title: current.title,
                      message: current.message,
                      severity: current.severity,
                      status: 'read',
                      createdAtUtc: current.createdAtUtc,
                      profileId: current.profileId,
                      ruleId: current.ruleId,
                    )
                  : current,
            )
            .toList(growable: false);
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to mark read: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final unreadCount = _items.where((item) => item.isUnread).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            onPressed: _isLoading ? null : _load,
            icon: _isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: NeuroColors.surface,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                const Icon(Icons.notifications_active_outlined,
                    color: NeuroColors.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Unread notifications: $unreadCount',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          if (_isLoading && _items.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 56),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_error != null && _items.isEmpty)
            _InfoCard(
              icon: Icons.cloud_off,
              text: 'Failed to load notifications: $_error',
            )
          else if (_items.isEmpty)
            const _InfoCard(
              icon: Icons.notifications_none,
              text:
                  'No notifications yet. After a few sessions, proactive follow-up items will appear here.',
            )
          else
            for (final item in _items)
              Card(
                margin: const EdgeInsets.only(bottom: 10),
                color: _severityBackground(item.severity),
                child: ListTile(
                  leading: Icon(
                    _severityIcon(item.severity, unread: item.isUnread),
                    color: _severityColor(item.severity, unread: item.isUnread),
                  ),
                  title: Text(
                    item.title,
                    style: TextStyle(
                      fontWeight:
                          item.severity.toLowerCase() == 'action_required'
                              ? FontWeight.w800
                              : FontWeight.w700,
                    ),
                  ),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 4),
                      Text(item.message),
                      const SizedBox(height: 6),
                      Text(
                        _formatTime(item.createdAtUtc),
                        style:
                            const TextStyle(color: NeuroColors.textSecondary),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        item.severity.toUpperCase().replaceAll('_', ' '),
                        style: TextStyle(
                          color: _severityColor(item.severity,
                              unread: item.isUnread),
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  trailing: item.isUnread
                      ? TextButton(
                          onPressed: () => _markRead(item),
                          child: const Text('Mark read'),
                        )
                      : const SizedBox.shrink(),
                ),
              ),
        ],
      ),
    );
  }

  static String _formatTime(String raw) {
    try {
      return DateFormat('dd MMM • HH:mm').format(DateTime.parse(raw).toLocal());
    } catch (_) {
      return raw;
    }
  }

  static IconData _severityIcon(String severity, {required bool unread}) {
    final value = severity.toLowerCase();
    if (value == 'warning') {
      return unread
          ? Icons.warning_amber_rounded
          : Icons.warning_amber_outlined;
    }
    if (value == 'action_required') {
      return unread
          ? Icons.priority_high_rounded
          : Icons.priority_high_outlined;
    }
    return unread ? Icons.mark_email_unread_outlined : Icons.drafts_outlined;
  }

  static Color _severityColor(String severity, {required bool unread}) {
    final value = severity.toLowerCase();
    if (value == 'warning') {
      return unread ? const Color(0xFFB26A00) : const Color(0xFF8A7B62);
    }
    if (value == 'action_required') {
      return unread ? const Color(0xFF9A2F2F) : const Color(0xFF7C5C5C);
    }
    return unread ? NeuroColors.primary : NeuroColors.textSecondary;
  }

  static Color? _severityBackground(String severity) {
    final value = severity.toLowerCase();
    if (value == 'warning') {
      return const Color(0xFFFFF7E8);
    }
    if (value == 'action_required') {
      return const Color(0xFFFFEFEF);
    }
    return null;
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.icon,
    required this.text,
  });

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: NeuroColors.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: NeuroColors.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: NeuroColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }
}
