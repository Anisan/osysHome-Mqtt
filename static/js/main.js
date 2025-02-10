new Vue({
    el: '#mqtt_app',
    delimiters: ['[[', ']]'], // Измененные разделители
    data: {
        topicTree: {},
        expandedState: {},
        only_linked: false,
        filterText:"",
        loading: true,
        socket:null,
    },
    async created() {
      await this.fetchTopics()
      this.restoreExpandedState(); // Восстановление состояния из localStorage
      this.only_linked = JSON.parse(localStorage.getItem('only_linked_mqtt')) || false;
      this.filterText = localStorage.getItem('filter_text_mqtt') ?? ''
      this.connectSocket(); 
    },
    mounted() {

    },
    watch: {
      only_linked(value){
        localStorage.setItem('only_linked_mqtt', JSON.stringify(value))
      },
      filterText(value){
        localStorage.setItem('filter_text_mqtt', value)
      }
    },
    computed: {
      filteredData(){
        if (this.only_linked || this.filterText != "") {
          return this.filterTree(this.topicTree)
        }
        return this.topicTree
      }
    },
    methods: {
      connectSocket() {
        this.socket = io(); // Подключаемся к серверу
        this.socket.emit('subscribeData',["Mqtt"]);
        this.socket.on('Mqtt', (data) => {
          if (data.operation == "updateTopic"){
            const updatedData = data.data
            //console.log('Received updated topics:', updatedData);
            // Обновляем данные в дереве
              const topic = updatedData['path']
              const parts = topic.split('/');
              let currentLevel = this.topicTree;
              for (let i = 0; i < parts.length - 1; i++) {
                var part = parts[i]
                if (part == "") part = "/"
                if (!currentLevel[part] || !currentLevel[part].children) {
                  currentLevel[part] = { children: {} };
                }
                currentLevel = currentLevel[part].children;
              }
              const leafKey = parts[parts.length - 1];
              currentLevel[leafKey]['value'] = updatedData['value']
              currentLevel[leafKey]['updated'] = updatedData['updated']
          }

        });
      },
        async fetchTopics() {
            this.loading = true
            try {
              const response = await axios.get('/api/mqtt/topics');
              this.topicTree = response.data;
            } catch (error) {
              console.error("Error fetching topics:", error);
            }
            this.loading = false
          },
          restoreExpandedState() {
            const savedState = localStorage.getItem('expandedStateMqtt');
            if (savedState) {
              this.expandedState = JSON.parse(savedState);
            }
          },
          saveExpandedState() {
            localStorage.setItem('expandedStateMqtt', JSON.stringify(this.expandedState));
          },
          clearFilter() {
            this.filterText = ''; // Очищаем поле фильтра
          },
          filterTree(tree) {
            const filter = this.filterText.toLowerCase();
            const filteredTree = {};
            for (const key in tree) {
              const value = tree[key];
              // Проверяем соответствие фильтру
              let match = false;
              if (filter == '') match = true;
              if (key.toLowerCase().includes(filter)) match = true;
              if (value.linked_object && value.linked_object.toLowerCase().includes(filter)) match = true;
              if (value.linked_property && value.linked_property.toLowerCase().includes(filter)) match = true;
              if (value.linked_method && value.linked_method.toLowerCase().includes(filter)) match = true;
              if (this.only_linked)
              {
                 const link = value.linked_object !== undefined && value.linked_object != null && value.linked_object != ""
                 match = match && link
              }

              if (match) {
                filteredTree[key] = { ...value }; // Добавляем текущий узел
              } else if (value.children) {
                const children = this.filterTree(value.children);
                if (Object.keys(children).length > 0) {
                  filteredTree[key] = { ...value, children }; // Добавляем узел с детьми
                }
              }
            }
            return filteredTree;
          },
    }
  });