import { useState } from 'react';
import { GraduationCap, Clock, CheckCircle, AlertCircle, BookOpen, ChevronRight, Award } from 'lucide-react';
import { COURSES, LEARNING_PATHS, LEARNING_STATS, COURSE_CATEGORIES, COURSE_STATUSES } from '@/data/learningData';
import type { CourseStatus, CourseLevel } from '@/data/learningData';

const STATUS_META: Record<CourseStatus, { label: string; cls: string; icon: React.ComponentType<{ size?: number; className?: string }> }> = {
  completed: { label: 'Completed', cls: 'bg-success/15 text-success-foreground', icon: CheckCircle },
  in_progress: { label: 'In Progress', cls: 'bg-info/15 text-info-foreground', icon: BookOpen },
  not_started: { label: 'Not Started', cls: 'bg-muted text-muted-foreground', icon: GraduationCap },
  mandatory: { label: 'Mandatory', cls: 'bg-destructive/15 text-destructive', icon: AlertCircle },
};

const LEVEL_CLS: Record<CourseLevel, string> = {
  Beginner: 'bg-success/10 text-success',
  Intermediate: 'bg-warning/10 text-warning',
  Advanced: 'bg-destructive/10 text-destructive',
};

function ProgressBar({ value, max = 100, color = '#4a7c3f' }: { value: number; max?: number; color?: string }) {
  return (
    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${(value / max) * 100}%`, backgroundColor: color }} />
    </div>
  );
}

export default function LearningHubPage() {
  const [activeTab, setActiveTab] = useState<'courses' | 'paths'>('courses');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const filtered = COURSES.filter(c => {
    if (categoryFilter && c.category !== categoryFilter) return false;
    if (statusFilter === 'Completed' && c.status !== 'completed') return false;
    if (statusFilter === 'In Progress' && c.status !== 'in_progress') return false;
    if (statusFilter === 'Not Started' && c.status !== 'not_started') return false;
    if (statusFilter === 'Mandatory' && !c.isMandatory) return false;
    return true;
  });

  return (
    <div className="fluid-section" data-testid="learning-hub-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-foreground">Learning Hub</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Airport training, certifications, and learning paths.</p>
        </div>
      </div>

      {/* Progress summary */}
      <div className="fluid-grid-sm mb-5">
        {[
          { label: 'Total Courses', value: LEARNING_STATS.totalCourses, icon: GraduationCap, color: '#4a7c3f' },
          { label: 'Completed', value: LEARNING_STATS.completedCourses, icon: CheckCircle, color: '#27ae60' },
          { label: 'In Progress', value: LEARNING_STATS.inProgress, icon: BookOpen, color: '#3b82f6' },
          { label: 'Mandatory Pending', value: LEARNING_STATS.mandatoryPending, icon: AlertCircle, color: '#e8820c' },
        ].map(stat => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="fluid-card responsive-card border border-border bg-card p-4 shadow-sm hover:shadow-md" data-testid={`learning-stat-${stat.label.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2" style={{ backgroundColor: stat.color + '20' }}>
                <Icon size={16} style={{ color: stat.color }} />
              </div>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              <p className="text-xs text-muted-foreground">{stat.label}</p>
            </div>
          );
        })}
      </div>

      {/* Overall progress */}
      <div className="responsive-card mb-5 border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-foreground">Overall Learning Progress</span>
          <span className="text-sm font-bold text-primary">{LEARNING_STATS.overallProgress}%</span>
        </div>
        <ProgressBar value={LEARNING_STATS.overallProgress} />
        <p className="text-xs text-[#7a9a72] mt-1">{LEARNING_STATS.completedCourses} of {LEARNING_STATS.totalCourses} courses completed</p>
      </div>

      {/* Tabs */}
      <div className="scrollbar-soft mb-4 flex w-full gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1 shadow-sm sm:w-fit">
        {(['courses', 'paths'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize ${activeTab === tab ? 'bg-[#4a7c3f] text-white' : 'text-muted-foreground hover:bg-accent'}`}
            data-testid={`tab-${tab}`}
          >
            {tab === 'courses' ? 'Courses' : 'Learning Paths'}
          </button>
        ))}
      </div>

      {activeTab === 'courses' && (
        <>
          {/* Filters */}
          <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 sm:max-w-xl">
            <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value === 'All Categories' ? '' : e.target.value)} className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring/30" data-testid="filter-category">
              {COURSE_CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value === 'All Statuses' ? '' : e.target.value)} className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring/30" data-testid="filter-status">
              {COURSE_STATUSES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div className="fluid-grid-lg">
            {filtered.map(course => {
              const { label: statusLabel, cls: statusCls, icon: StatusIcon } = STATUS_META[course.status];
              return (
                <div key={course.id} className="fluid-card responsive-card flex min-w-0 flex-col gap-3 border border-border bg-card p-5 shadow-sm hover:border-primary hover:shadow-md" data-testid={`course-${course.id}`}>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-foreground leading-snug flex-1">{course.title}</h3>
                    {course.isMandatory && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-destructive/10 text-destructive border border-red-100 font-medium whitespace-nowrap flex-shrink-0">Mandatory</span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${LEVEL_CLS[course.level]}`}>{course.level}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent text-primary">{course.category}</span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock size={11} /> {course.duration}</span>
                    <span className="flex items-center gap-1"><GraduationCap size={11} /> {course.instructor}</span>
                  </div>

                  {course.status !== 'not_started' && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Progress</span>
                        <span className="text-xs font-semibold text-primary">{course.progress}%</span>
                      </div>
                      <ProgressBar value={course.progress} color={course.status === 'completed' ? '#27ae60' : '#4a7c3f'} />
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1 border-t border-border">
                    <span className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${statusCls}`}>
                      <StatusIcon size={11} />
                      {statusLabel}
                    </span>
                    {course.dueDate && course.status !== 'completed' && (
                      <span className="text-[10px] text-warning">Due {course.dueDate}</span>
                    )}
                    {course.completionDate && (
                      <span className="text-[10px] text-success flex items-center gap-1"><Award size={10} /> {course.completionDate}</span>
                    )}
                  </div>

                  <button className={`w-full py-2 rounded-lg text-xs font-semibold transition-colors ${course.status === 'completed' ? 'bg-accent text-primary' : 'bg-[#4a7c3f] text-white hover:bg-[#2d4f22]'}`} data-testid={`btn-${course.id}`}>
                    {course.status === 'completed' ? 'Review Course' : course.status === 'in_progress' ? 'Continue' : 'Start Course'}
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}

      {activeTab === 'paths' && (
        <div className="fluid-grid-lg">
          {LEARNING_PATHS.map(path => (
            <div key={path.id} className="fluid-card responsive-card flex min-w-0 flex-col gap-3 border border-border bg-card p-5 shadow-sm hover:border-primary hover:shadow-md" data-testid={`path-${path.id}`}>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center">
                <GraduationCap size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground">{path.title}</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{path.description}</p>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>{path.courseCount} courses</span>
                <span>{path.estimatedHours}h total</span>
                <span className="text-primary font-medium">{path.department}</span>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">{path.completedCount}/{path.courseCount} completed</span>
                  <span className="text-xs font-semibold text-primary">{Math.round((path.completedCount / path.courseCount) * 100)}%</span>
                </div>
                <ProgressBar value={path.completedCount} max={path.courseCount} />
              </div>
              <button className="flex items-center justify-center gap-1 w-full py-2 rounded-lg bg-accent text-primary text-xs font-semibold hover:bg-accent transition-colors">
                View Path <ChevronRight size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
