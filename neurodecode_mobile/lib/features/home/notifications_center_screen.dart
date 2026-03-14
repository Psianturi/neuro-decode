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
                child: ListTile(
                  leading: Icon(
                    item.isUnread
                        ? Icons.mark_email_unread_outlined
                        : Icons.drafts_outlined,
                    color: item.isUnread
                        ? NeuroColors.primary
                        : NeuroColors.textSecondary,
                  ),
                  title: Text(item.title),
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
