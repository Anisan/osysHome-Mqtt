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
        connectionStatus: "unknown",
        reconnectAttempts: 0,
    },
    async created() {
      await this.fetchTopics()
      this.restoreExpandedState(); // Восстановление состояния из localStorage
      this.only_linked = JSON.parse(localStorage.getItem('only_linked_mqtt')) || false;
      this.filterText = localStorage.getItem('filter_text_mqtt') ?? ''
      this.connectSocket();
      this.fetchConnectionStatus();
      // Обновляем статус каждые 5 секунд
      setInterval(() => {
        this.fetchConnectionStatus();
      }, 5000);
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
      },
      connectionStatusClass() {
        const status = this.connectionStatus.toLowerCase();
        if (status === 'connected') return 'bg-success';
        if (status === 'connecting') return 'bg-warning';
        if (status === 'error') return 'bg-danger';
        return 'bg-secondary';
      },
      connectionStatusIcon() {
        const status = this.connectionStatus.toLowerCase();
        if (status === 'connected') return 'fa-circle-check';
        if (status === 'connecting') return 'fa-circle-notch fa-spin';
        if (status === 'error') return 'fa-circle-exclamation';
        return 'fa-circle-question';
      },
      connectionStatusText() {
        const status = this.connectionStatus.toLowerCase();
        const texts = {
          'connected': 'Подключено к MQTT брокеру',
          'connecting': 'Подключение к MQTT брокеру...',
          'disconnected': 'Отключено от MQTT брокера',
          'error': 'Ошибка подключения к MQTT брокеру',
          'unknown': 'Статус подключения неизвестен'
        };
        return texts[status] || texts['unknown'];
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
          } else if (data.operation == "connectionStatus") {
            // Обновляем статус подключения из WebSocket
            const statusData = data.data;
            this.connectionStatus = statusData.status || 'unknown';
            this.reconnectAttempts = statusData.reconnect_attempts || 0;
          }
        });
      },
      async fetchConnectionStatus() {
        try {
          const response = await axios.get('/api/mqtt/status');
          if (response.data) {
            this.connectionStatus = response.data.status || 'unknown';
            this.reconnectAttempts = response.data.reconnect_attempts || 0;
          }
        } catch (error) {
          console.error("Error fetching connection status:", error);
          this.connectionStatus = 'error';
        }
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