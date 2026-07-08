import { DashboardBlock } from '../types';

export const DASHBOARD_BLOCKS: DashboardBlock[] = [
  { id: 'recentDocuments', title: 'Recent Documents', component: 'RecentDocumentsBlock', colSpan: 2, visible: true },
  { id: 'popularSearches', title: 'Popular Searches', component: 'PopularSearchesBlock', colSpan: 1, visible: true },
  { id: 'expertSpotlight', title: 'Expert Spotlight', component: 'ExpertSpotlightBlock', colSpan: 1, visible: true },
  { id: 'aiConversations', title: 'Recent AI Conversations', component: 'AIConversationsBlock', colSpan: 2, visible: true },
  { id: 'knowledgeGaps', title: 'Knowledge Gaps', component: 'KnowledgeGapsBlock', colSpan: 1, visible: true },
  { id: 'topContributors', title: 'Top Contributors', component: 'TopContributorsBlock', colSpan: 1, visible: true },
  { id: 'announcements', title: 'Announcements', component: 'AnnouncementsBlock', colSpan: 2, visible: true },
];
