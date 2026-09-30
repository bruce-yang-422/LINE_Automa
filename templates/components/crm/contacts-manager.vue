<template>
  <div class="apple-hig-container">
    <!-- 頂部統計卡片 -->
    <section class="stats-cards mb-6">
      <div class="stat-card" v-for="stat in stats" :key="stat.id">
        <div class="stat-icon" :class="stat.iconClass">{{ stat.icon }}</div>
        <div class="stat-value" :class="stat.valueClass">{{ formatNumber(stat.value) }}</div>
        <div class="stat-label" v-html="stat.label"></div>
      </div>
    </section>

    <!-- 篩選器 -->
    <div class="filter-section">
      <h3 class="text-lg font-semibold mb-3">篩選收件者</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div 
          v-for="(option, index) in filters" 
          :key="index"
          class="filter-option" 
          :class="{ active: selectedFilter === option.value }"
          @click="selectedFilter = option.value">
          {{ option.label }}
        </div>
      </div>
    </div>

    <!-- 收件者列表 -->
    <section class="crm-list">
      <h3 class="text-xl font-semibold mb-4">所有收件者</h3>
      
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" v-if="contacts.length > 0">
        <div 
          v-for="(contact, index) in contacts" 
          :key="contact.id"
          class="crm-card"
          :class="{ 'is-loading': contact.is_loading }">
          
          <!-- 組織標籤區 -->
          <div class="org-chips">
            <span 
              v-for="tag in contact.tags" 
              :key="tag.name"
              class="organization-badge"
              :class="'org-' + tag.type">
              {{ tag.name }}
            </span>
          </div>

          <!-- 狀態指示器 -->
          <div 
            v-if="contact.status"
            class="status-indicator"
            :class="'status-' + contact.status.toLowerCase()">
          </div>

          <!-- 個人資料卡片 -->
          <div class="profile-card">
            <img 
              :src="contact.avatar_url || '/api/placeholder/64/64'" 
              alt="{{ contact.display_name }}"
              class="w-24 h-24 rounded-full border-4 border-white shadow-md"
            />
          </div>

          <!-- 姓名 -->
          <h4 class="text-lg font-semibold mb-1">{{ contact.display_name }}</h4>
          
          <!-- 職位/職稱 -->
          <p v-if="contact.job_title" class="text-sm text-gray-500 mb-3">
            {{ contact.job_title }}
          </p>

          <!-- 詳細資訊 -->
          <div class="detail-grid grid grid-cols-2 gap-y-2 text-sm">
            <div v-for="(item, i) in getContactDetails(contact)" :key="i" class="detail-item">
              <span class="text-gray-500 mr-2">{{ item.label }}</span>
              <span class="text-gray-900">{{ item.value }}</span>
            </div>
          </div>

          <!-- 進度條 (如果存在) -->
          <div v-if="contact.progress" class="mt-3">
            <div class="flex justify-between text-xs mb-1">
              <span>{{ contact.progress.current }} / {{ contact.progress.total }}</span>
              <span>{{ formatPercentage(contact.progress.percent) }}%</span>
            </div>
            <div class="progress-bar">
              <div 
                class="progress-fill"
                :class="getProgressClass(contact.progress.percent)"
                :style="{ width: contact.progress.percent + '%' }">
              </div>
            </div>
          </div>

          <!-- 動作按鈕 -->
          <div class="action-buttons mt-4 pt-3 border-t border-gray-100">
            <button 
              v-if="contact.is_active"
              class="btn-primary btn-sm"
              :disabled="contact.is_loading || contact.action_disabled"
              @click.stop="handleContactAction(contact)">
              {{ contact.action_label }}
            </button>
            
            <span 
              v-else-if="contact.status === 'inactive'"
              class="text-sm text-gray-500">
              此收件者已無效
            </span>

            <!-- 更多動作 -->
            <div class="more-actions mt-2 flex gap-2" v-if="showMoreActions(contact)">
              <button 
                v-for="(action, idx) in contact.more_actions || []" 
                :key="idx"
                class="btn-secondary btn-xs px-3 py-1 text-xs rounded-full"
                @click.stop="handleContactAction(contact, action)">
                {{ action }}
              </button>
            </div>
          </div>

          <!-- 載入動畫 -->
          <div v-if="contact.is_loading && !contact.data" class="loading-overlay">
            <span class="loading-spinner"></span>
          </div>
        </div>
      </div>

      <!-- 空狀態 -->
      <div 
        v-else-if="!filteringContacts || filteringContacts.length === 0"
        class="empty-state text-center py-12">
        <div class="text-4xl mb-3">📬</div>
        <h3 class="text-lg font-semibold text-gray-700 mb-1">
          {{ !filteringContacts ? '暫無收件者' : '符合條件的收件者' }}
        </h3>
        <p class="text-gray-500 max-w-md mx-auto">
          {{ filteringContacts ? '請調整篩選條件以查看更多收件者。' : '開始添加收件者以建立您的聯絡人清單。' }}
        </p>
      </div>

      <!-- 載入中 -->
      <div v-else class="text-center py-12">
        <div class="loading-spinner mx-auto"></div>
      </div>
    </section>

    <!-- 排序控制 -->
    <section class="sorting-control mt-6">
      <label for="sort-select" class="text-sm font-medium text-gray-700 mb-2 block">
        排序方式：{{ sortLabel }}
      </label>
      <select 
        id="sort-select"
        v-model="sortBy"
        class="w-full md:w-auto px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="name_asc">姓名 (A-Z)</option>
        <option value="name_desc">姓名 (Z-A)</option>
        <option value="email_asc">電子郵件</option>
        <option value="date_added_newest">新增時間 (最新)</option>
        <option value="date_added_oldest">新增時間 (最早)</option>
      </select>
    </section>

  </div>
  </div>
</template>

<script>
export default {
  name: 'ContactsManager',
  data() {
    return {
      contacts: [],
      stats: [
        { id: 1, icon: '👥', iconClass: 'bg-blue-100 text-blue-600', value: 128, label: '<strong>總收件者數</strong><br><span class="text-gray-500">已建立聯絡關係' </span> },
        { id: 2, icon: '💼', iconClass: 'bg-purple-100 text-purple-600', value: 4, label: '<strong>組織標籤</strong><br><span class="text-gray-500">涵蓋多個部門' </span> },
        { id: 3, icon: '✅', iconClass: 'bg-green-100 text-green-600', value: 98, label: '<strong>活躍狀態</strong><br><span class="text-gray-500">近期有互動' </span> },
        { id: 4, icon: '⏰', iconClass: 'bg-yellow-100 text-yellow-600', value: 30, label: '<strong>待處理</strong><br><span class="text-gray-500">需要後續聯繫' </span> }
      ],
      filters: [
        { label: '全部', value: 'all' },
        { label: '活躍', value: 'active' },
        { label: '未分類', value: 'uncategorized' },
        { label: '高級搜尋', value: 'advanced' }
      ],
      selectedFilter: 'all',
      sortBy: 'name_asc',
      sortOptions: ['name_asc', 'name_desc', 'email_asc', 'date_added_newest', 'date_added_oldest'],
      filterLabels: {
        name_asc: '姓名 (A-Z)',
        name_desc: '姓名 (Z-A)',
        email_asc: '電子郵件',
        date_added_newest: '新增時間 (最新)',
        date_added_oldest: '新增時間 (最早)'
      },
      showFilters: true,
      searchQuery: '',
      pagination: {
        currentPage: 1,
        itemsPerPage: 9
      }
    };
  },
  computed: {
    sortLabel() {
      return this.filterLabels[this.sortBy] || '姓名 (A-Z)';
    },
    filteringContacts() {
      let filtered = [...this.contacts];
      
      // 搜尋
      if (this.searchQuery) {
        const query = this.searchQuery.toLowerCase();
        filtered = filtered.filter(contact => 
          contact.display_name.toLowerCase().includes(query) ||
          contact.email.toLowerCase().includes(query) ||
          contact.job_title?.toLowerCase().includes(query)
        );
      }
      
      // 篩選器
      if (this.selectedFilter !== 'all') {
        const statusMap = {
          active: ['active'],
          uncategorized: ['uncategorized', 'other'],
          advanced: ['high_priority', 'vip']
        };
        
        filtered = filtered.filter(contact => {
          if (!contact.tags) return false;
          const hasMatchingTag = statusMap[this.selectedFilter]?.some(t => 
            contact.tags.some(tag => tag.name === t || tag.type === t)
          );
          return hasMatchingTag || this.selectedFilter === 'active' && contact.is_active;
        });
      }
      
      // 排序
      filtered.sort((a, b) => {
        if (this.sortBy === 'name_asc') return a.display_name.localeCompare(b.display_name);
        if (this.sortBy === 'name_desc') return b.display_name.localeCompare(a.display_name);
        if (this.sortBy === 'email_asc') return a.email.localeCompare(b.email);
        if (this.sortBy === 'date_added_newest') return b.date_added - a.date_added;
        if (this.sortBy === 'date_added_oldest') return a.date_added - b.date_added;
        return 0;
      });
      
      return filtered;
    }
  },
  methods: {
    formatNumber(value) {
      return new Intl.NumberFormat('zh-TW').format(value);
    },
    
    formatPercentage(value) {
      return Number(value).toFixed(0);
    },
    
    getProgressClass(percent) {
      if (percent >= 75) return 'bg-green-500';
      if (percent >= 50) return 'bg-blue-500';
      if (percent >= 25) return 'bg-yellow-500';
      return 'bg-red-500';
    },
    
    getContactDetails(contact) {
      const details = [];
      
      if (contact.phone) {
        details.push({ label: '電話', value: contact.phone });
      }
      if (contact.job_title) {
        details.push({ label: '職位', value: contact.job_title });
      }
      if (contact.department) {
        details.push({ label: '部門', value: contact.department });
      }
      
      return details;
    },
    
    showMoreActions(contact) {
      return ['標記已讀', '發送通知', '查看詳情'].some(a => contact.actions?.includes(a));
    },
    
    handleContactAction(contact, actionName) {
      // TODO: 處理收件者動作
      console.log(`執行動作 ${actionName} 於 ${contact.display_name}`);
    },
    
    toggleFilter() {
      this.showFilters = !this.showFilters;
    }
  },
  
  mounted() {
    // 初始化測試資料
    this.initDemoData();
  },
  
  updated() {
    // 動態更新統計數據
    this.updateStats();
  },
  
  watch: {
    contacts(newContacts) {
      this.updateStats();
    }
  }
};
</script>

<style scoped>
/* 這裡可以加一些 Vue 單元件獨有的樣式 */
.loading-spinner {
  display: inline-block;
  width: 2rem;
  height: 2rem;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  background-color: #f9fafb;
  border-radius: 1rem;
  border: 2px dashed #e5e7eb;
}

.crm-list .crm-card {
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
</template>