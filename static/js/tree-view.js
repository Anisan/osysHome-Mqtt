Vue.component('tree-view', {
    delimiters: ['{{', '}}'],
    props: ['data', 'expandedState'],
    data() {
        return {
            search: '',
            isOpen: false,
            selectedKey: null,
            initialSet: true
        };
    },
    watch: {
        value(newVal) {
            console.log(newVal)
            this.selectedKey = newVal;
        },
        selectedKey(newVal) {
            if (!this.initialSet) {
                this.$emit('changed', newVal);
            }
            this.$emit('input', newVal);
            this.initialSet = false; // После первого изменения установим в false
        }
    },
    computed: {
        filteredOptions() {
            return Object.keys(this.options).filter(key => 
                (key + this.options[key]).toLowerCase().includes(this.search.toLowerCase())
            );
            
        },
        selectedDescription() {
            return this.selectedKey ? this.selectedKey + " - " + this.options[this.selectedKey] : this.placeholder;
        }
    },
    methods: {
        hasChildren(value) {
            return value.children && Object.keys(value.children).length > 0;
          },
          isExpanded(key) {
            return this.expandedState[key] === true;
          },
          toggle(key) {
            if (this.hasChildren(this.data[key])) {
              this.$set(this.expandedState, key, !this.isExpanded(key)); // Обновляем состояние
              this.$emit('save-expanded-state'); // Сохраняем состояние
            }
          },
          formatDate(timestamp) {
            const date = new Date(timestamp * 1000); // Преобразуем timestamp в миллисекунды
            return date.toLocaleString(); // Возвращаем форматированную дату
          }
    },
    mounted() {
        document.addEventListener('click', this.handleClickOutside);
        this.selectedKey = this.value;
    },
    beforeDestroy() {
        document.removeEventListener('click', this.handleClickOutside);
    },
    template: `
    <ul class="tree">
      <li v-for="(value, key) in data" :key="key">
        <div @click="toggle(key)" class="d-flex align-items-center">
            <i v-if="hasChildren(value) && !isExpanded(key)" class="fas fa-folder me-2" style="font-size: 1.2rem;"></i>
            <i v-if="hasChildren(value) && isExpanded(key)" class="fas fa-folder-open me-2" style="font-size: 1.2rem;"></i>
            <a v-if="value.id" :href="'?op=edit&topic='+value.id">{{ key }}</a>
            <strong v-else>{{ key }}</strong>
            
            <!-- Если это листовой узел, отображаем значение и время -->
            <span v-if="value.id" class="ms-2">
                <span class="tree-value">: {{ value.value }} </span>
                <span v-if="value.linked_object" class="tree-link">({{ value.linked_object }}.{{value.linked_property}}{{value.linked_method}})</span>
                <a :href="'?op=delete&topic='+value.id" onClick="return confirm('Are you sure? Please confirm.')" title="Delete" class="link"><i class="feather icon-trash text-danger"></i></a>
            </span>
        </div>
        <!-- Если есть дочерние элементы и они развернуты, отображаем их -->
        <tree-view v-if="value.children && isExpanded(key)" 
                   :data="value.children" 
                   :expanded-state="expandedState"
                   @save-expanded-state="$emit('save-expanded-state')"></tree-view>
      </li>
    </ul>
    `
});